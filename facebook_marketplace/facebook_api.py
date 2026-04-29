"""
Facebook Marketplace scraper using direct HTTP requests + cookies.
No Playwright/browser needed — works on Render, Railway, etc.
"""
from __future__ import annotations

import json
import math
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent
COOKIES_FILE = ROOT / "fb_cookies.json"
COOKIE_PROFILES_FILE = ROOT / "fb_cookie_profiles.json"
LEGACY_TALCA_COOKIES_FILE = ROOT / "fb_cookies_talca.json"
COOKIE_PROFILE_NAMES = ("curico", "talca")
DEFAULT_COOKIE_PROFILE = "curico"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

REQUIRED_COOKIE_KEYS = ("c_user", "xs")
OPTIONAL_COOKIE_KEYS = ("datr", "fr", "sb", "wd", "locale", "presence")

CACHE_GEO: dict[str, tuple[float, float, str]] = {}
CURICO_LATITUDE = -34.98749193781055
CURICO_LONGITUDE = -71.24675716218236
TALCA_LATITUDE = -35.4264
TALCA_LONGITUDE = -71.6554
SANTIAGO_LATITUDE = -33.4489
SANTIAGO_LONGITUDE = -70.6693
CURICO_TO_TALCA_RADIUS_KM = 75
KNOWN_CHILE_LOCATIONS = {
    "curico": (CURICO_LATITUDE, CURICO_LONGITUDE, "Curico, Maule, Chile"),
    "curico maule": (CURICO_LATITUDE, CURICO_LONGITUDE, "Curico, Maule, Chile"),
    "talca": (TALCA_LATITUDE, TALCA_LONGITUDE, "Talca, Maule, Chile"),
    "talca maule": (TALCA_LATITUDE, TALCA_LONGITUDE, "Talca, Maule, Chile"),
    "santiago": (SANTIAGO_LATITUDE, SANTIAGO_LONGITUDE, "Santiago, Region Metropolitana, Chile"),
    "santiago region metropolitana": (SANTIAGO_LATITUDE, SANTIAGO_LONGITUDE, "Santiago, Region Metropolitana, Chile"),
    "molina": (-35.1143, -71.2823, "Molina, Maule, Chile"),
    "molina maule": (-35.1143, -71.2823, "Molina, Maule, Chile"),
    "rauco": (-34.9252, -71.3180, "Rauco, Maule, Chile"),
    "rauco maule": (-34.9252, -71.3180, "Rauco, Maule, Chile"),
    "romeral": (-34.9627, -71.1252, "Romeral, Maule, Chile"),
    "romeral maule": (-34.9627, -71.1252, "Romeral, Maule, Chile"),
    "teno": (-34.8708, -71.1621, "Teno, Maule, Chile"),
    "teno maule": (-34.8708, -71.1621, "Teno, Maule, Chile"),
}

COUNTRY_NAMES = {"CL": "Chile"}
CHILE_REGION_ALIASES = {
    "AP": "Arica y Parinacota", "TA": "Tarapaca", "AN": "Antofagasta",
    "AT": "Atacama", "CO": "Coquimbo", "VS": "Valparaiso",
    "RM": "Region Metropolitana de Santiago", "LI": "O'Higgins",
    "ML": "Maule", "NB": "Nuble", "BI": "Biobio",
    "AR": "La Araucania", "LR": "Los Rios", "LL": "Los Lagos",
    "AI": "Aysen", "MA": "Magallanes",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SearchOptions:
    query: str
    marketplace_path: str = "curico"
    limit: int = 40
    max_pages: int = 3
    min_price: int = 0
    max_price: int = 0
    word: str = ""
    include_words: list[str] = field(default_factory=list)
    exclude_words: list[str] = field(default_factory=list)
    location_query: str = "Curico, Maule, Chile"
    latitude: float | None = -34.98749193781055
    longitude: float | None = -71.24675716218236
    radius_km: int = 12
    include_talca: bool = False
    country_code: str = "CL"


@dataclass
class SearchResult:
    items: list[dict[str, Any]]
    all_items: list[dict[str, Any]]
    total_matches: int
    captured_raw: int
    filter_breakdown: dict[str, Any]


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def normalize_text(value: str) -> str:
    return " ".join(str(value or "").lower().split())

def strip_accents(value: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))

def _extract_city_name(label: str) -> str:
    first = str(label or "").split(",")[0].strip()
    return normalize_text(strip_accents(first))


def _location_cache_key(label: str) -> str:
    parts = [strip_accents(part).strip().lower() for part in str(label or "").split(",")]
    compact = " ".join(part for part in parts[:2] if part)
    return re.sub(r"[^a-z0-9]+", " ", compact).strip()


def _search_fetch_radius_km(opts: SearchOptions) -> int:
    return opts.radius_km


def _city_priority(location: str, target_city: str, include_talca: bool) -> int:
    city = _extract_city_name(location)
    if city and city == _extract_city_name(target_city):
        return 0
    if include_talca and city == "talca":
        return 1
    return 2


def _distance_sort_value(item: dict[str, Any]) -> float:
    value = item.get("distance_km")
    if value is None or value == "":
        return 9999.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 9999.0


# ---------------------------------------------------------------------------
# Cookie management
# ---------------------------------------------------------------------------

def _normalize_profile_name(profile: str | None) -> str:
    cleaned = normalize_text(strip_accents(str(profile or "")))
    return "talca" if cleaned == "talca" else "curico"


def _normalize_cookie_map(cookies: dict[str, Any]) -> dict[str, str]:
    if not isinstance(cookies, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in cookies.items():
        k = str(key).strip()
        v = str(value).strip()
        if k and v:
            out[k] = v
    return out


def _empty_cookie_profiles() -> dict[str, dict[str, str]]:
    return {name: {} for name in COOKIE_PROFILE_NAMES}


def _looks_like_cookie_map(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    return bool(data) and all(isinstance(k, str) and isinstance(v, str) for k, v in data.items())


def load_cookie_profiles() -> dict[str, dict[str, str]]:
    """Load cookie profiles from disk (curico/talca) with legacy fallbacks."""
    profiles = _empty_cookie_profiles()

    if COOKIE_PROFILES_FILE.exists():
        try:
            raw = json.loads(COOKIE_PROFILES_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for name in COOKIE_PROFILE_NAMES:
                    profiles[name] = _normalize_cookie_map(raw.get(name) or {})
                return profiles
        except Exception:
            pass

    # Backward compatibility: legacy single file = curico profile.
    if COOKIES_FILE.exists():
        try:
            legacy = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
            if isinstance(legacy, dict):
                # If this file already contains profiles structure, keep it.
                if any(isinstance(legacy.get(name), dict) for name in COOKIE_PROFILE_NAMES):
                    for name in COOKIE_PROFILE_NAMES:
                        profiles[name] = _normalize_cookie_map(legacy.get(name) or {})
                else:
                    profiles["curico"] = _normalize_cookie_map(legacy)
        except Exception:
            pass

    # Additional compatibility: old standalone talca file.
    if LEGACY_TALCA_COOKIES_FILE.exists():
        try:
            talca_legacy = json.loads(LEGACY_TALCA_COOKIES_FILE.read_text(encoding="utf-8"))
            if isinstance(talca_legacy, dict):
                talca_map = _normalize_cookie_map(talca_legacy)
                if talca_map:
                    profiles["talca"] = talca_map
        except Exception:
            pass

    # If only legacy files exist, materialize the new profiles file so future reads
    # and UI status checks use the same canonical storage.
    if not COOKIE_PROFILES_FILE.exists() and any(profiles[name] for name in COOKIE_PROFILE_NAMES):
        try:
            COOKIE_PROFILES_FILE.write_text(
                json.dumps(profiles, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    return profiles


def save_cookie_profiles(profiles: dict[str, dict[str, str]]) -> None:
    normalized = _empty_cookie_profiles()
    for name in COOKIE_PROFILE_NAMES:
        normalized[name] = _normalize_cookie_map((profiles or {}).get(name) or {})

    COOKIE_PROFILES_FILE.write_text(
        json.dumps(normalized, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    # Keep curico profile in old file for compatibility with scripts/tests.
    COOKIES_FILE.write_text(
        json.dumps(normalized.get("curico") or {}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_cookies(profile: str | None = None) -> dict[str, str]:
    """Load cookies for a profile (default: curico)."""
    selected = _normalize_profile_name(profile)
    return load_cookie_profiles().get(selected, {})


def save_cookies(cookies: dict[str, str], profile: str | None = None) -> None:
    """Save cookies for a profile (default: curico)."""
    selected = _normalize_profile_name(profile)
    profiles = load_cookie_profiles()
    profiles[selected] = _normalize_cookie_map(cookies)
    save_cookie_profiles(profiles)


def parse_cookie_string(raw: str) -> dict[str, str]:
    """Parse a raw cookie string (from browser dev tools) into a dict."""
    cookies: dict[str, str] = {}
    for part in str(raw or "").split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        key = key.strip()
        value = value.strip()
        if key and value:
            cookies[key] = value
    return cookies


def validate_cookies(cookies: dict[str, str]) -> tuple[bool, str]:
    """Check that required cookies are present."""
    if not cookies:
        return False, "No hay cookies configuradas."
    missing = [k for k in REQUIRED_COOKIE_KEYS if not cookies.get(k)]
    if missing:
        hint = ""
        if "xs" in missing and cookies.get("c_user"):
            hint = (
                " La cookie 'xs' es HttpOnly y NO aparece con document.cookie. "
                "Debes copiarla desde F12 → Application → Cookies → facebook.com."
            )
        return False, f"Faltan cookies requeridas: {', '.join(missing)}.{hint}"
    return True, "Cookies OK"


def _build_cookie_header(cookies: dict[str, str]) -> str:
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _http_get(url: str, cookies: dict[str, str], timeout: int = 25) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-CL,es;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cookie": _build_cookie_header(cookies),
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    }
    req = Request(url, headers=headers)
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _http_post_graphql(
    url: str,
    cookies: dict[str, str],
    data: dict[str, str],
    timeout: int = 20,
) -> str:
    body = urlencode(data).encode("utf-8")
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Accept-Language": "es-CL,es;q=0.9,en-US;q=0.8,en;q=0.7",
        "Content-Type": "application/x-www-form-urlencoded",
        "Cookie": _build_cookie_header(cookies),
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "X-FB-Friendly-Name": "CometMarketplaceSearchContentContainerQuery",
    }
    req = Request(url, data=body, headers=headers, method="POST")
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Facebook HTML / data extraction
# ---------------------------------------------------------------------------

def _extract_fb_dtsg(html: str) -> str | None:
    patterns = [
        r'"DTSGInitialData"\s*,\s*\[\]\s*,\s*\{"token"\s*:\s*"([^"]+)"',
        r'"dtsg"\s*:\s*\{"token"\s*:\s*"([^"]+)"',
        r'name="fb_dtsg"\s+value="([^"]+)"',
    ]
    for pat in patterns:
        m = re.search(pat, html)
        if m:
            return m.group(1)
    return None


def _deep_find_edges(obj: Any, depth: int = 0) -> list[dict]:
    """Recursively find MarketplaceFeedListingStoryObject edges."""
    if depth > 20:
        return []
    edges_found: list[dict] = []

    if isinstance(obj, str):
        stripped = obj.strip()
        if stripped.startswith("{") and "marketplace" in obj.lower():
            try:
                parsed = json.loads(stripped)
                edges_found.extend(_deep_find_edges(parsed, depth + 1))
            except (json.JSONDecodeError, RecursionError):
                pass
        return edges_found

    if isinstance(obj, dict):
        if obj.get("__typename") == "MarketplaceFeedListingStoryObject":
            edges_found.append({"node": obj})
        edges = obj.get("edges")
        if isinstance(edges, list):
            for edge in edges:
                if not isinstance(edge, dict):
                    continue
                node = edge.get("node")
                if isinstance(node, dict) and node.get("__typename") == "MarketplaceFeedListingStoryObject":
                    edges_found.append(edge)
        for v in obj.values():
            edges_found.extend(_deep_find_edges(v, depth + 1))

    elif isinstance(obj, list):
        for item in obj:
            edges_found.extend(_deep_find_edges(item, depth + 1))

    return edges_found


def _extract_page_info(obj: Any, depth: int = 0) -> dict | None:
    """Find page_info with has_next_page and end_cursor."""
    if depth > 20:
        return None
    if isinstance(obj, dict):
        pi = obj.get("page_info")
        if isinstance(pi, dict) and "has_next_page" in pi:
            return pi
        for v in obj.values():
            result = _extract_page_info(v, depth + 1)
            if result:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = _extract_page_info(item, depth + 1)
            if result:
                return result
    elif isinstance(obj, str) and obj.strip().startswith("{"):
        try:
            parsed = json.loads(obj)
            return _extract_page_info(parsed, depth + 1)
        except (json.JSONDecodeError, RecursionError):
            pass
    return None


def _listing_from_edge(edge: dict) -> dict[str, Any] | None:
    """Convert a GraphQL edge to a listing dict."""
    node = (edge or {}).get("node") or {}
    listing = node.get("listing") or node
    listing_id = str(listing.get("id") or "").strip()
    title = str(listing.get("marketplace_listing_title") or "").strip()
    if not listing_id or not title:
        return None

    reverse_geocode = (listing.get("location") or {}).get("reverse_geocode") or {}
    city = str(reverse_geocode.get("city") or "").strip()
    state = str(reverse_geocode.get("state") or "").strip()
    location = ", ".join(p for p in (city, state) if p)

    price_obj = listing.get("listing_price") or {}
    price = str(price_obj.get("formatted_amount") or "").strip()
    strike = str((listing.get("strikethrough_price") or {}).get("formatted_amount") or "").strip()
    if not price and strike:
        price = strike

    image = str(
        (((listing.get("primary_listing_photo") or {}).get("image") or {}).get("uri") or "")
    ).strip()

    listed = ""
    if listing.get("if_gk_just_listed_tag_on_search_feed"):
        listed = "Recién publicado"

    return {
        "title": title,
        "price": price,
        "strikethrough_price": strike,
        "location": location,
        "listed": listed,
        "description": "",
        "link": f"https://www.facebook.com/marketplace/item/{listing_id}/",
        "image": image,
    }


def _extract_listings_from_html(html: str) -> tuple[list[dict], str | None, list[Any]]:
    """Extract listings + next cursor + raw payloads from Facebook HTML."""
    all_payloads: list[Any] = []

    # Method 1: <script type="application/json" data-sjs>
    for m in re.finditer(
        r'<script[^>]*type="application/json"[^>]*data-sjs[^>]*>(.*?)</script>',
        html, re.DOTALL,
    ):
        try:
            all_payloads.append(json.loads(m.group(1)))
        except json.JSONDecodeError:
            pass

    # Method 2: <script data-content-len ...>
    for m in re.finditer(
        r'<script[^>]*data-content-len="[^"]*"[^>]*>(.*?)</script>',
        html, re.DOTALL,
    ):
        try:
            all_payloads.append(json.loads(m.group(1)))
        except json.JSONDecodeError:
            pass

    # Method 3: Broader search for script tags containing marketplace data
    if not all_payloads:
        for m in re.finditer(r'<script[^>]*>(.*?)</script>', html, re.DOTALL):
            content = m.group(1).strip()
            if "MarketplaceFeed" not in content and "marketplace_search" not in content:
                continue
            for jm in re.finditer(r'(\{"__bbox":\{.*)', content):
                candidate = jm.group(1)
                depth = 0
                end = 0
                for i, ch in enumerate(candidate):
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            end = i + 1
                            break
                if end > 0:
                    try:
                        all_payloads.append(json.loads(candidate[:end]))
                    except json.JSONDecodeError:
                        pass

    # Extract edges from all payloads
    seen_ids: set[str] = set()
    listings: list[dict] = []
    for payload in all_payloads:
        edges = _deep_find_edges(payload)
        for edge in edges:
            item = _listing_from_edge(edge)
            if not item:
                continue
            if item["link"] in seen_ids:
                continue
            seen_ids.add(item["link"])
            listings.append(item)

    # Extract cursor
    cursor = None
    for payload in all_payloads:
        pi = _extract_page_info(payload)
        if pi and pi.get("has_next_page"):
            cursor = pi.get("end_cursor")
            break

    return listings, cursor, all_payloads


def _extract_relay_query_info(payloads: list[Any]) -> tuple[str | None, dict | None]:
    """Extract doc_id and variables from relay preloader data in the HTML payloads."""
    doc_id = None
    variables = None

    def _search(obj: Any, depth: int = 0) -> None:
        nonlocal doc_id, variables
        if depth > 15 or (doc_id and variables):
            return

        if isinstance(obj, dict):
            qid = obj.get("queryID") or obj.get("query_id") or obj.get("id")
            if isinstance(qid, str) and qid.isdigit() and len(qid) > 10:
                preloader = obj.get("preloaderID", "")
                if isinstance(preloader, str) and "ContentContainer" in preloader:
                    doc_id = qid
                    variables = obj.get("variables")

            for v in obj.values():
                _search(v, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                _search(item, depth + 1)

    for payload in payloads:
        _search(payload)
        if doc_id:
            break

    return doc_id, variables


def _fetch_graphql_page(
    cookies: dict[str, str],
    fb_dtsg: str,
    doc_id: str,
    cursor: str,
    user_id: str,
    base_variables: dict[str, Any],
) -> tuple[list[dict], str | None]:
    """Fetch the next page of marketplace results via GraphQL POST."""
    variables = dict(base_variables)
    variables["cursor"] = cursor
    variables["count"] = 24

    data = {
        "fb_dtsg": fb_dtsg,
        "doc_id": doc_id,
        "variables": json.dumps(variables),
        "__user": user_id,
        "__a": "1",
        "__comet_req": "15",
        "server_timestamps": "true",
    }

    try:
        raw = _http_post_graphql("https://www.facebook.com/api/graphql/", cookies, data, timeout=15)
    except Exception:
        return [], None

    # Parse multi-line JSON response
    items: list[dict] = []
    seen: set[str] = set()
    next_cursor = None

    for line in raw.splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue

        edges = _deep_find_edges(payload)
        for edge in edges:
            item = _listing_from_edge(edge)
            if item and item["link"] not in seen:
                seen.add(item["link"])
                items.append(item)

        pi = _extract_page_info(payload)
        if pi:
            if pi.get("has_next_page"):
                next_cursor = pi.get("end_cursor")
            else:
                next_cursor = None

    return items, next_cursor


# ---------------------------------------------------------------------------
# Geocoding (reused from original)
# ---------------------------------------------------------------------------

def _geocode_open_meteo(query: str, country_code: str) -> dict | None:
    params = {"name": query, "count": 1, "language": "es", "format": "json"}
    if country_code.strip():
        params["countryCode"] = country_code.strip().upper()
    req = Request(
        f"https://geocoding-api.open-meteo.com/v1/search?{urlencode(params)}",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    results = data.get("results") or []
    return results[0] if results else None


def geocode_location(query: str, country_code: str = "CL") -> tuple[float, float, str]:
    cleaned = str(query or "").strip()
    if not cleaned:
        raise ValueError("Ubicacion vacia.")
    if country_code.strip().upper() == "CL":
        known = KNOWN_CHILE_LOCATIONS.get(_location_cache_key(cleaned))
        if known:
            return known
    cache_key = f"{cleaned}|{country_code.upper()}"
    cached = CACHE_GEO.get(cache_key)
    if cached:
        return cached

    first = _geocode_open_meteo(cleaned, country_code)
    if first:
        lat = float(first["latitude"])
        lon = float(first["longitude"])
        parts = [
            str(first.get("name") or "").strip(),
            str(first.get("admin1") or "").strip(),
            str(first.get("country") or "").strip(),
        ]
        label = ", ".join(p for p in parts if p)
        CACHE_GEO[cache_key] = (lat, lon, label)
        return lat, lon, label
    raise RuntimeError(f"No pude geocodificar: {cleaned}")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

def _parse_price(text: str | None) -> int | None:
    if not text:
        return None
    digits = "".join(ch for ch in str(text) if ch.isdigit())
    return int(digits) if digits else None


def apply_filters(items: list[dict], opts: SearchOptions) -> list[dict]:
    word_lc = normalize_text(opts.word)
    inc = [normalize_text(w) for w in opts.include_words if w.strip()]
    exc = [normalize_text(w) for w in opts.exclude_words if w.strip()]
    out: list[dict] = []
    for item in items:
        title = normalize_text(item.get("title", ""))
        pv = _parse_price(item.get("price"))
        if opts.min_price > 0 and (pv is None or pv < opts.min_price):
            continue
        if opts.max_price > 0 and (pv is None or pv > opts.max_price):
            continue
        if word_lc and word_lc not in title:
            continue
        if inc and not all(w in title for w in inc):
            continue
        if exc and any(w in title for w in exc):
            continue
        out.append(item)
    return out


def apply_location_filter(
    items: list[dict],
    lat: float | None,
    lon: float | None,
    radius_km: int,
    country_code: str,
    target_city: str = "",
    include_talca: bool = False,
) -> list[dict]:
    norm_city = _extract_city_name(target_city)
    allowed_extra_cities = {"talca"} if include_talca else set()
    if lat is None or lon is None or radius_km <= 0:
        return items

    locations_to_geocode: set[str] = set()
    for item in items:
        loc = str(item.get("location") or "").strip()
        city = _extract_city_name(loc)
        if (
            loc
            and not (norm_city and city == norm_city)
            and city not in allowed_extra_cities
        ):
            locations_to_geocode.add(loc)

    geocoded_locations: dict[str, tuple[float, float, str] | None] = {}
    if locations_to_geocode:
        workers = min(8, len(locations_to_geocode))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_location = {
                executor.submit(geocode_location, loc, country_code): loc
                for loc in locations_to_geocode
            }
            for future in as_completed(future_to_location):
                loc = future_to_location[future]
                try:
                    geocoded_locations[loc] = future.result()
                except Exception:
                    geocoded_locations[loc] = None

    out: list[dict] = []
    for item in items:
        loc = str(item.get("location") or "").strip()
        if not loc:
            out.append(item)
            continue
        if norm_city and _extract_city_name(loc) == norm_city:
            item["distance_km"] = 0.0
            out.append(item)
            continue
        if _extract_city_name(loc) in allowed_extra_cities:
            item["distance_km"] = round(haversine_km(lat, lon, TALCA_LATITUDE, TALCA_LONGITUDE), 2)
            out.append(item)
            continue
        resolved = geocoded_locations.get(loc)
        if resolved is None:
            out.append(item)
            continue
        iloc, ilon, _ = resolved
        dist = haversine_km(lat, lon, iloc, ilon)
        if dist <= radius_km:
            item["distance_km"] = round(dist, 2)
            out.append(item)
    return out


# ---------------------------------------------------------------------------
# URL building
# ---------------------------------------------------------------------------

def build_search_url(opts: SearchOptions) -> str:
    params: list[tuple[str, str]] = [("query", opts.query.strip()), ("exact", "false")]
    if opts.min_price > 0:
        params.append(("minPrice", str(opts.min_price)))
    if opts.max_price > 0:
        params.append(("maxPrice", str(opts.max_price)))
    if opts.latitude is not None and opts.longitude is not None:
        params.append(("latitude", f"{opts.latitude:.6f}"))
        params.append(("longitude", f"{opts.longitude:.6f}"))
    fetch_radius_km = _search_fetch_radius_km(opts)
    if fetch_radius_km > 0:
        params.append(("radiusKM", str(fetch_radius_km)))
    base = opts.marketplace_path.strip("/")
    path = f"{base}/search" if base else "search"
    return f"https://www.facebook.com/marketplace/{path}/?{urlencode(params)}"


def _search_variants(opts: SearchOptions) -> list[tuple[str, SearchOptions]]:
    variants: list[tuple[str, SearchOptions]] = [("base", opts)]
    if opts.include_talca and _extract_city_name(opts.location_query) == "curico":
        variants.append(
            (
                "talca",
                SearchOptions(
                    query=opts.query,
                    marketplace_path="talca",
                    limit=opts.limit,
                    max_pages=opts.max_pages,
                    min_price=opts.min_price,
                    max_price=opts.max_price,
                    word=opts.word,
                    include_words=list(opts.include_words),
                    exclude_words=list(opts.exclude_words),
                    location_query="Talca, Maule, Chile",
                    latitude=TALCA_LATITUDE,
                    longitude=TALCA_LONGITUDE,
                    radius_km=opts.radius_km,
                    include_talca=False,
                    country_code=opts.country_code,
                ),
            )
        )
    return variants


def _resolve_profile_for_options(opts: SearchOptions) -> str:
    base = normalize_text(strip_accents(opts.marketplace_path or ""))
    city = _extract_city_name(opts.location_query)
    if "talca" in base or city == "talca":
        return "talca"
    return "curico"


def _fetch_variant_listings(
    variant_name: str,
    opts: SearchOptions,
    cookies: dict[str, str],
    cookie_profile: str,
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    url = build_search_url(opts)
    html = _http_get(url, cookies)

    lower_html = html[:5000].lower()
    if "login" in lower_html and ("id=\"email\"" in lower_html or "name=\"email\"" in lower_html):
        raise RuntimeError(
            "Facebook redirigió al login. Las cookies expiraron o son inválidas. "
            "Actualiza las cookies desde la configuración."
        )

    listings, cursor, payloads = _extract_listings_from_html(html)
    seen_links = {item["link"] for item in listings}
    initial_count = len(listings)

    fb_dtsg = _extract_fb_dtsg(html)
    doc_id, relay_vars = _extract_relay_query_info(payloads)
    user_id = cookies.get("c_user", "")
    buy_location = relay_vars.get("buyLocation") if isinstance(relay_vars, dict) else None

    requested_buy_location = None
    if opts.latitude is not None and opts.longitude is not None:
        requested_buy_location = {
            "latitude": round(float(opts.latitude), 6),
            "longitude": round(float(opts.longitude), 6),
        }

    detected_buy_location = None
    if isinstance(buy_location, dict):
        try:
            detected_buy_location = {
                "latitude": round(float(buy_location["latitude"]), 6),
                "longitude": round(float(buy_location["longitude"]), 6),
            }
        except Exception:
            detected_buy_location = buy_location

    pagination_debug = {
        "variant": variant_name,
        "cookie_profile": cookie_profile,
        "search_url": url,
        "marketplace_path": opts.marketplace_path,
        "location_query": opts.location_query,
        "requested_buy_location": requested_buy_location,
        "detected_buy_location": detected_buy_location,
        "session_location_locked": (
            requested_buy_location is not None
            and detected_buy_location is not None
            and requested_buy_location != detected_buy_location
        ),
        "has_fb_dtsg": bool(fb_dtsg),
        "has_doc_id": bool(doc_id),
        "doc_id_found": doc_id[:20] + "..." if doc_id and len(doc_id) > 20 else doc_id,
        "has_cursor": bool(cursor),
        "has_user_id": bool(user_id),
        "initial_count": initial_count,
        "pages_fetched": 0,
        "payloads_parsed": len(payloads),
    }

    max_pages = max(0, min(int(opts.max_pages), 5))
    if fb_dtsg and doc_id and cursor and user_id and isinstance(relay_vars, dict):
        empty_pages = 0
        for page_idx in range(max_pages):
            page_items, next_cursor = _fetch_graphql_page(
                cookies=cookies,
                fb_dtsg=fb_dtsg,
                doc_id=doc_id,
                cursor=cursor,
                user_id=user_id,
                base_variables=relay_vars,
            )
            pagination_debug["pages_fetched"] = page_idx + 1
            new_count = 0
            for item in page_items:
                if item["link"] in seen_links:
                    continue
                seen_links.add(item["link"])
                listings.append(item)
                new_count += 1

            if new_count == 0:
                empty_pages += 1
            else:
                empty_pages = 0

            if not next_cursor or empty_pages >= 2:
                break
            cursor = next_cursor

    for item in listings:
        item["marketplace_variant"] = variant_name
        item["marketplace_path_used"] = opts.marketplace_path
        item["cookie_profile_used"] = cookie_profile

    return variant_name, listings, pagination_debug


# ---------------------------------------------------------------------------
# Main search
# ---------------------------------------------------------------------------

def execute_search(opts: SearchOptions, cookies: dict[str, str] | dict[str, dict[str, str]]) -> SearchResult:
    profile_cookies: dict[str, dict[str, str]]
    if _looks_like_cookie_map(cookies):
        profile_cookies = _empty_cookie_profiles()
        profile_cookies["curico"] = _normalize_cookie_map(cookies)  # legacy mode
    else:
        profile_cookies = _empty_cookie_profiles()
        if isinstance(cookies, dict):
            for name in COOKIE_PROFILE_NAMES:
                profile_cookies[name] = _normalize_cookie_map((cookies or {}).get(name) or {})

    # Resolve location
    lat, lon, loc_label = opts.latitude, opts.longitude, opts.location_query
    if lat is None or lon is None:
        if opts.location_query.strip():
            lat, lon, loc_label = geocode_location(opts.location_query, opts.country_code)

    variants = _search_variants(opts)
    merged_listings: list[dict[str, Any]] = []
    seen_links: set[str] = set()
    variant_debug: list[dict[str, Any]] = []

    variant_runs: list[tuple[str, SearchOptions, dict[str, str], str]] = []
    for variant_name, variant_opts in variants:
        profile_name = _resolve_profile_for_options(variant_opts)
        variant_cookies = profile_cookies.get(profile_name, {})
        valid, msg = validate_cookies(variant_cookies)
        if not valid:
            raise RuntimeError(
                f"Perfil '{profile_name}' sin cookies válidas. {msg} "
                f"Configura ese perfil en la sección de cookies."
            )
        variant_runs.append((variant_name, variant_opts, variant_cookies, profile_name))

    workers = min(2, len(variant_runs))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_variant = {
            executor.submit(
                _fetch_variant_listings,
                variant_name,
                variant_opts,
                variant_cookies,
                profile_name,
            ): variant_name
            for variant_name, variant_opts, variant_cookies, profile_name in variant_runs
        }
        for future in as_completed(future_to_variant):
            _variant_name, listings, debug = future.result()
            variant_debug.append(debug)
            for item in listings:
                if item["link"] in seen_links:
                    continue
                seen_links.add(item["link"])
                merged_listings.append(item)

    captured_raw = len(merged_listings)

    # Apply filters
    filtered = apply_filters(merged_listings, opts)
    after_text = len(filtered)

    # Apply location filter
    final = apply_location_filter(
        filtered, lat, lon, opts.radius_km, opts.country_code, loc_label, opts.include_talca,
    )
    final = sorted(
        enumerate(final),
        key=lambda pair: (
            _city_priority(str(pair[1].get("location") or ""), loc_label, opts.include_talca),
            _distance_sort_value(pair[1]),
            pair[0],
        ),
    )
    final = [item for _, item in final]

    total = len(final)
    items = final[: opts.limit]

    for idx, item in enumerate(items, start=1):
        item["position"] = idx
        if loc_label:
            zone = f"{loc_label} ({opts.radius_km} km)"
            if opts.include_talca:
                zone = f"{zone} + Talca"
            item["search_location"] = (
                zone if opts.radius_km > 0 else loc_label
            )

    return SearchResult(
        items=items,
        all_items=final,
        total_matches=total,
        captured_raw=captured_raw,
        filter_breakdown={
            "captured_raw": captured_raw,
            "after_text_price_filters": after_text,
            "after_location_filter": total,
            "search_url": build_search_url(opts),
            "resolved_location": loc_label,
            "include_talca": opts.include_talca,
            "fetch_radius_km": _search_fetch_radius_km(opts),
            "variants": sorted(variant_debug, key=lambda item: item["variant"]),
        },
    )


# ---------------------------------------------------------------------------
# Excel export (reused from original)
# ---------------------------------------------------------------------------

def xml_escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")


def build_xlsx_bytes(items: list[dict]) -> bytes:
    headers = ["Posicion", "Titulo", "Precio", "Ubicacion", "ZonaBusqueda", "Publicado", "Descripcion", "Link"]
    rows: list[list] = [headers]
    for idx, item in enumerate(items, start=1):
        rows.append([
            idx,
            str(item.get("title") or ""),
            str(item.get("price") or ""),
            str(item.get("location") or ""),
            str(item.get("search_location") or ""),
            str(item.get("listed") or ""),
            str(item.get("description") or ""),
            str(item.get("link") or ""),
        ])

    sheet_rows: list[str] = []
    for r_idx, row in enumerate(rows, start=1):
        cells: list[str] = []
        for c_idx, val in enumerate(row, start=1):
            col = ""
            n = c_idx
            while n:
                n, rem = divmod(n - 1, 26)
                col = chr(65 + rem) + col
            ref = f"{col}{r_idx}"
            if isinstance(val, int):
                cells.append(f'<c r="{ref}"><v>{val}</v></c>')
            else:
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{xml_escape(str(val))}</t></is></c>')
        sheet_rows.append(f'<row r="{r_idx}">{"".join(cells)}</row>')

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Resultados" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )
    wb_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '</Relationships>'
    )
    ct_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '</Types>'
    )
    buf = BytesIO()
    with ZipFile(buf, mode="w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", ct_xml)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", wb_rels_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return buf.getvalue()


def export_xlsx(items: list[dict], query: str, output_path: str | None = None) -> Path:
    if output_path and output_path != "__AUTO__":
        out = Path(output_path)
    else:
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", query)[:40].strip("_") or "busqueda"
        out = ROOT / "exports" / f"fbm_{safe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(build_xlsx_bytes(items))
    return out

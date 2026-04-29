from __future__ import annotations

import argparse
import json
import math
import re
import sys
import threading
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen
from zipfile import ZIP_DEFLATED, ZipFile

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
DEFAULT_MARKETPLACE_PATH = "curico"
DEFAULT_LOCATION_QUERY = "Curico, Maule, Chile"
DEFAULT_LATITUDE = -34.98749193781055
DEFAULT_LONGITUDE = -71.24675716218236
CACHE_GEO: dict[str, tuple[float, float, str]] = {}
CURRENCY_RE = re.compile(
    r"(?i)(?:[$]|clp|ars|usd|mxn|cop|pen)\s*[\d\.\,]+|[\d\.\,]+\s*(?:[$]|clp|ars|usd|mxn|cop|pen)"
)
META_LINE_RE = re.compile(
    r"(?i)\b(hora|horas|dia|dias|semana|semanas|mes|meses|minute|minutes|hour|hours|day|days|week|weeks|month|months)\b"
)
COUNTRY_NAMES = {
    "CL": "Chile",
}
CHILE_REGION_ALIASES = {
    "AP": "Arica y Parinacota",
    "TA": "Tarapaca",
    "AN": "Antofagasta",
    "AT": "Atacama",
    "CO": "Coquimbo",
    "VS": "Valparaiso",
    "RM": "Region Metropolitana de Santiago",
    "LI": "O'Higgins",
    "ML": "Maule",
    "NB": "Nuble",
    "BI": "Biobio",
    "AR": "La Araucania",
    "LR": "Los Rios",
    "LL": "Los Lagos",
    "AI": "Aysen",
    "MA": "Magallanes",
}


@dataclass
class SearchOptions:
    query: str
    marketplace_path: str = DEFAULT_MARKETPLACE_PATH
    limit: int = 40
    scroll_limit: int = 24
    min_price: int = 0
    max_price: int = 0
    word: str = ""
    include_words: list[str] | None = None
    exclude_words: list[str] | None = None
    include_description: bool = False
    storage_state: str | None = None
    user_data_dir: str | None = None
    search_url: str | None = None
    location_query: str = DEFAULT_LOCATION_QUERY
    latitude: float | None = DEFAULT_LATITUDE
    longitude: float | None = DEFAULT_LONGITUDE
    radius_km: int = 12
    country_code: str = "CL"
    show_browser: bool = False
    timeout_seconds: int = 30


@dataclass
class SearchExecutionResult:
    items: list[dict[str, Any]]
    all_items: list[dict[str, Any]]
    total_matches: int
    observed_matches: int
    source: str
    filter_breakdown: dict[str, Any]


def normalize_text(value: str) -> str:
    return " ".join(str(value or "").lower().split())


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def text_has_term(text: str, term: str) -> bool:
    term = normalize_text(term)
    if not term:
        return False
    return term in text


def _country_name_from_code(country_code: str) -> str:
    normalized_code = str(country_code or "").strip().upper()
    return COUNTRY_NAMES.get(normalized_code, normalized_code)


def _location_query_variants(location_query: str, country_code: str) -> list[str]:
    cleaned_query = str(location_query or "").strip()
    if not cleaned_query:
        return []

    variants: list[str] = []
    seen: set[str] = set()

    def add_variant(value: str) -> None:
        candidate = str(value or "").strip(" ,")
        if not candidate:
            return
        key = normalize_text(strip_accents(candidate))
        if key in seen:
            return
        seen.add(key)
        variants.append(candidate)

    parts = [part.strip() for part in cleaned_query.split(",") if part.strip()]
    first_part = parts[0] if parts else cleaned_query
    first_no_accents = strip_accents(first_part)
    country_name = _country_name_from_code(country_code)

    add_variant(cleaned_query)
    add_variant(strip_accents(cleaned_query))
    add_variant(first_part)
    add_variant(first_no_accents)

    if country_name:
        add_variant(f"{first_part}, {country_name}")
        add_variant(f"{first_no_accents}, {country_name}")

    if len(parts) >= 2:
        second_part = parts[1]
        second_no_accents = strip_accents(second_part)
        second_abbrev = re.sub(r"[^A-Za-z]", "", second_part).upper()
        expanded_region = ""
        if str(country_code or "").strip().upper() == "CL":
            expanded_region = CHILE_REGION_ALIASES.get(second_abbrev, "")

        add_variant(f"{first_part}, {second_part}")
        add_variant(f"{first_no_accents}, {second_no_accents}")
        if country_name:
            add_variant(f"{first_part}, {second_part}, {country_name}")
            add_variant(f"{first_no_accents}, {second_no_accents}, {country_name}")
        if expanded_region:
            expanded_region_no_accents = strip_accents(expanded_region)
            add_variant(f"{first_part}, {expanded_region}")
            add_variant(f"{first_no_accents}, {expanded_region_no_accents}")
            if country_name:
                add_variant(f"{first_part}, {expanded_region}, {country_name}")
                add_variant(f"{first_no_accents}, {expanded_region_no_accents}, {country_name}")

    return variants


def _geocode_with_open_meteo(query: str, country_code: str) -> dict[str, Any] | None:
    params = {
        "name": query,
        "count": 1,
        "language": "es",
        "format": "json",
    }
    if country_code.strip():
        params["countryCode"] = country_code.strip().upper()

    request = Request(
        f"https://geocoding-api.open-meteo.com/v1/search?{urlencode(params)}",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urlopen(request, timeout=30) as response:
        payload = json.load(response)
    results = payload.get("results") or []
    return results[0] if results else None


def _geocode_with_nominatim(query: str, country_code: str) -> dict[str, Any] | None:
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": 1,
    }
    if country_code.strip():
        params["countrycodes"] = country_code.strip().lower()

    request = Request(
        f"https://nominatim.openstreetmap.org/search?{urlencode(params)}",
        headers={"User-Agent": "Mozilla/5.0 Codex FacebookMarketplace/1.0"},
    )
    with urlopen(request, timeout=30) as response:
        payload = json.load(response)
    return payload[0] if payload else None


def geocode_location(location_query: str, country_code: str = "CL") -> tuple[float, float, str]:
    cleaned_query = str(location_query or "").strip()
    if not cleaned_query:
        raise ValueError("Debes indicar una ubicacion para usar radio.")

    cache_key = f"{cleaned_query}|{country_code.upper()}"
    cached = CACHE_GEO.get(cache_key)
    if cached is not None:
        return cached

    query_variants = _location_query_variants(cleaned_query, country_code)

    for variant in query_variants:
        first = _geocode_with_open_meteo(variant, country_code)
        if first is not None:
            latitude = float(first["latitude"])
            longitude = float(first["longitude"])
            label_parts = [
                str(first.get("name") or "").strip(),
                str(first.get("admin2") or "").strip(),
                str(first.get("admin1") or "").strip(),
                str(first.get("country") or "").strip(),
            ]
            label = ", ".join([part for part in label_parts if part])
            CACHE_GEO[cache_key] = (latitude, longitude, label)
            return CACHE_GEO[cache_key]

    for variant in query_variants:
        first = _geocode_with_nominatim(variant, country_code)
        if first is not None:
            latitude = float(first["lat"])
            longitude = float(first["lon"])
            label = str(first.get("display_name") or variant).strip()
            CACHE_GEO[cache_key] = (latitude, longitude, label)
            return CACHE_GEO[cache_key]

    if query_variants:
        fallback_variant = query_variants[0]
        if fallback_variant != cleaned_query:
            raise RuntimeError(
                f"No pude geocodificar la ubicacion: {cleaned_query} (ni usando variante {fallback_variant})"
            )
    raise RuntimeError(f"No pude geocodificar la ubicacion: {cleaned_query}")


def resolve_search_location(options: SearchOptions) -> tuple[float | None, float | None, str]:
    if options.latitude is not None and options.longitude is not None:
        label = options.location_query.strip() or f"{options.latitude}, {options.longitude}"
        return float(options.latitude), float(options.longitude), label
    if options.location_query.strip():
        return geocode_location(options.location_query, options.country_code)
    return None, None, ""


def validate_storage_state(storage_state: str | None) -> None:
    raw = str(storage_state or "").strip()
    if not raw:
        return

    state_path = Path(raw)
    if not state_path.exists():
        raise FileNotFoundError(f"No existe storage_state: {state_path}")

    payload = json.loads(state_path.read_text(encoding="utf-8"))
    cookies = payload.get("cookies") or []
    origins = payload.get("origins") or []
    has_c_user = any(cookie.get("name") == "c_user" and cookie.get("value") for cookie in cookies)
    if not has_c_user:
        raise RuntimeError(
            "El storage_state no tiene sesion autenticada de Facebook. "
            "Vuelve a generar storage_state.json con login completo."
        )
    if len(cookies) <= 2 and not origins:
        raise RuntimeError(
            "El storage_state actual solo contiene cookies minimas (por ejemplo c_user/xs) y no un "
            "estado completo de Playwright. Ese archivo no esta sirviendo para Marketplace. "
            "Regeneralo con `python login_facebook.py`, entra manualmente a Marketplace antes de presionar Enter, "
            "o deja vacio 'Archivo storage state' para probar con un perfil persistente valido."
        )


def build_search_url(
    query: str,
    marketplace_path: str,
    min_price: int,
    max_price: int,
    latitude: float | None = None,
    longitude: float | None = None,
    radius_km: int = 0,
) -> str:
    params: list[tuple[str, str]] = [("query", query.strip()), ("exact", "false")]
    if min_price > 0:
        params.append(("minPrice", str(min_price)))
    if max_price > 0:
        params.append(("maxPrice", str(max_price)))
    if latitude is not None and longitude is not None:
        params.append(("latitude", f"{latitude:.6f}"))
        params.append(("longitude", f"{longitude:.6f}"))
    if radius_km > 0:
        params.append(("radiusKM", str(radius_km)))

    base_segment = marketplace_path.strip("/")
    base_path = f"{base_segment}/search" if base_segment else "search"
    return f"https://www.facebook.com/marketplace/{base_path}/?{urlencode(params)}"


def search_url_has_native_location_filter(url: str) -> bool:
    parsed = urlparse(str(url or "").strip())
    query = parse_qs(parsed.query)
    return bool(query.get("latitude") and query.get("longitude"))


def detach_browser_for_manual_inspection(
    page: Any,
    context: Any,
    browser: Any,
    playwright_instance: Any,
    poll_interval_seconds: float = 0.5,
) -> None:
    def cleanup_when_closed() -> None:
        try:
            while True:
                try:
                    if page.is_closed():
                        break
                except Exception:
                    break
                try:
                    live_browser = browser or context.browser
                    if live_browser is not None and not live_browser.is_connected():
                        break
                except Exception:
                    break
                time.sleep(poll_interval_seconds)
        finally:
            try:
                context.close()
            except Exception:
                pass
            try:
                if browser is not None:
                    browser.close()
            except Exception:
                pass
            try:
                playwright_instance.stop()
            except Exception:
                pass

    threading.Thread(target=cleanup_when_closed, daemon=True).start()


def _extract_price_line(lines: list[str]) -> str | None:
    for line in lines:
        if CURRENCY_RE.search(line):
            return line.strip()
    return None


def _is_noise_line(line: str) -> bool:
    raw = normalize_text(line)
    if not raw:
        return True
    if raw in {"nuevo", "usado", "gratis", "free", "sponsored", "patrocinado"}:
        return True
    if META_LINE_RE.search(raw):
        return True
    if len(raw) <= 2:
        return True
    return False


def _is_listing_meta_line(line: str) -> bool:
    raw = normalize_text(line)
    if not raw:
        return False
    if raw.startswith("reci") and "public" in raw:
        return True
    return bool(META_LINE_RE.search(raw))


def _looks_like_location_line(line: str) -> bool:
    raw = " ".join(str(line or "").split()).strip()
    if not raw:
        return False
    if CURRENCY_RE.search(raw):
        return False
    return "," in raw


def _extract_title_line(lines: list[str], price_lines: list[str]) -> str:
    skip = {normalize_text(price_line) for price_line in price_lines}
    for line in lines:
        normalized = normalize_text(line)
        if normalized in skip:
            continue
        if _is_listing_meta_line(line):
            continue
        if _looks_like_location_line(line):
            continue
        if _is_noise_line(line):
            continue
        return " ".join(line.split()).strip()
    return ""


def _extract_location_and_age(
    lines: list[str], price_lines: list[str], title_line: str | None
) -> tuple[str, str]:
    price_norms = {normalize_text(price_line) for price_line in price_lines}
    title_norm = normalize_text(title_line)
    location = ""
    listed = ""
    for line in lines:
        normalized = normalize_text(line)
        if not normalized or normalized == title_norm or normalized in price_norms:
            continue
        if _is_listing_meta_line(line) and not listed:
            listed = " ".join(line.split()).strip()
            continue
        if not location and _looks_like_location_line(line):
            location = " ".join(line.split()).strip()
    return location, listed


def parse_price_value(price_text: str | None) -> int | None:
    if not price_text:
        return None
    digits = "".join(ch for ch in str(price_text) if ch.isdigit())
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_km = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return earth_radius_km * c


def apply_location_radius_filter(
    items: list[dict[str, Any]],
    target_latitude: float | None,
    target_longitude: float | None,
    radius_km: int,
    country_code: str,
    target_city: str = "",
) -> list[dict[str, Any]]:
    normalized_target_city = _extract_city_name(target_city)

    if target_latitude is None or target_longitude is None or radius_km <= 0:
        return items

    filtered: list[dict[str, Any]] = []
    for item in items:
        location = str(item.get("location") or "").strip()
        if not location:
            # Items without location data are kept (benefit of the doubt).
            filtered.append(item)
            continue

        # If the city name matches textually, include the item directly
        # without needing geocoding — avoids silent drops on API timeouts/errors.
        if normalized_target_city and _extract_city_name(location) == normalized_target_city:
            item["resolved_location"] = location
            item["distance_km"] = 0.0
            filtered.append(item)
            continue

        try:
            item_latitude, item_longitude, resolved_label = geocode_location(location, country_code)
        except Exception:
            # Geocoding failed — keep the item rather than silently dropping it.
            filtered.append(item)
            continue

        distance_km = haversine_km(target_latitude, target_longitude, item_latitude, item_longitude)
        if distance_km > radius_km:
            continue

        item["resolved_location"] = resolved_label
        item["distance_km"] = round(distance_km, 2)
        filtered.append(item)

    return filtered


def apply_filters(
    items: list[dict[str, Any]],
    min_price: int,
    max_price: int,
    word: str,
    include_words: list[str],
    exclude_words: list[str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    word_lc = normalize_text(word)
    include_lc = [normalize_text(w) for w in include_words if str(w).strip()]
    exclude_lc = [normalize_text(w) for w in exclude_words if str(w).strip()]
    for item in items:
        title = normalize_text(item.get("title", ""))
        price_value = parse_price_value(item.get("price"))
        if min_price > 0 and (price_value is None or price_value < min_price):
            continue
        if max_price > 0 and (price_value is None or price_value > max_price):
            continue
        if word_lc and not text_has_term(title, word_lc):
            continue
        if include_lc and not all(text_has_term(title, token) for token in include_lc):
            continue
        if exclude_lc and any(text_has_term(title, token) for token in exclude_lc):
            continue
        out.append(item)
    return out


def _js_collect_cards() -> str:
    return """
() => {
  const anchors = Array.from(document.querySelectorAll('a[href*="/marketplace/item/"]'));
  const rows = [];
  for (const anchor of anchors) {
    let node = anchor;
    for (let i = 0; i < 4; i += 1) {
      if (!node.parentElement) break;
      const candidate = node.parentElement;
      const text = (candidate.innerText || candidate.textContent || '').trim();
      if (text && text.length <= 420) {
        node = candidate;
      } else {
        break;
      }
    }
    const text = (node.innerText || node.textContent || '').trim();
    const img = node.querySelector('img')?.src || anchor.querySelector('img')?.src || '';
    rows.push({
      href: anchor.href,
      text,
      image: img,
    });
  }
  return rows;
}
"""


def _clean_card_text(raw_text: str) -> list[str]:
    seen: set[str] = set()
    lines: list[str] = []
    for line in str(raw_text or "").splitlines():
        value = " ".join(line.split()).strip()
        if not value:
            continue
        key = normalize_text(value)
        if key in seen:
            continue
        seen.add(key)
        lines.append(value)
    return lines


def _extract_city_name(location_label: str) -> str:
    first = str(location_label or "").split(",")[0].strip()
    return normalize_text(strip_accents(first))


def _js_collect_local_section_links() -> str:
    return """
() => {
  const normalize = (value) =>
    (value || '')
      .normalize('NFD')
      .replace(/[\\u0300-\\u036f]/g, '')
      .toLowerCase()
      .replace(/\\s+/g, ' ')
      .trim();

  const headingNeedle = 'resultados relacionados fuera de tu busqueda';
  let cutoff = null;
  const currentY = window.scrollY;
  for (const node of Array.from(document.querySelectorAll('span, div, h1, h2, h3'))) {
    const text = normalize(node.innerText || node.textContent || '');
    if (!text.includes(headingNeedle)) continue;
    const rect = node.getBoundingClientRect();
    const top = Math.round(rect.top + currentY);
    if (top <= currentY + 200) continue;
    if (cutoff === null || top < cutoff) {
      cutoff = top;
    }
  }

  const rows = [];
  const seen = new Set();
  for (const anchor of Array.from(document.querySelectorAll('a[href*="/marketplace/item/"]'))) {
    const href = (anchor.href || '').split('?', 1)[0];
    if (!href || seen.has(href)) continue;
    const rect = anchor.getBoundingClientRect();
    const top = Math.round(rect.top + window.scrollY);
    if (cutoff !== null && top >= cutoff) continue;
    seen.add(href);
    rows.push({ href, top });
  }
  return { cutoff, rows };
}
"""


def _parse_card(card: dict[str, Any]) -> dict[str, Any] | None:
    href = str(card.get("href") or "").strip()
    if "/marketplace/item/" not in href:
        return None

    lines = _clean_card_text(str(card.get("text") or ""))
    price_lines = [line.strip() for line in lines if CURRENCY_RE.search(line)]
    price_line = price_lines[0] if price_lines else None
    title_line = _extract_title_line(lines, price_lines)
    location, listed = _extract_location_and_age(lines, price_lines, title_line)
    if not title_line:
        return None

    return {
        "title": title_line,
        "price": price_line or "",
        "location": location,
        "listed": listed,
        "description": "",
        "link": href.split("?", 1)[0],
        "image": str(card.get("image") or ""),
    }


def _parse_graphql_response_chunks(raw_text: str) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for line in str(raw_text or "").splitlines():
        value = line.strip()
        if not value or not value.startswith("{"):
            continue
        try:
            chunks.append(json.loads(value))
        except json.JSONDecodeError:
            continue
    return chunks


def _listing_from_graphql_edge(edge: dict[str, Any]) -> dict[str, Any] | None:
    node = (edge or {}).get("node") or {}
    if node.get("__typename") != "MarketplaceFeedListingStoryObject":
        return None

    listing = node.get("listing") or {}
    listing_id = str(listing.get("id") or "").strip()
    title = str(listing.get("marketplace_listing_title") or "").strip()
    if not listing_id or not title:
        return None

    reverse_geocode = (listing.get("location") or {}).get("reverse_geocode") or {}
    city = str(reverse_geocode.get("city") or "").strip()
    state = str(reverse_geocode.get("state") or "").strip()
    location = ", ".join([part for part in (city, state) if part])

    price = str((listing.get("listing_price") or {}).get("formatted_amount") or "").strip()
    strikethrough_price = str((listing.get("strikethrough_price") or {}).get("formatted_amount") or "").strip()
    if not price and strikethrough_price:
        price = strikethrough_price

    image = (
        str(
            (((listing.get("primary_listing_photo") or {}).get("image") or {}).get("uri") or "")
        ).strip()
    )
    listed = ""
    if listing.get("if_gk_just_listed_tag_on_search_feed"):
        listed = "Recién publicado"

    return {
        "title": title,
        "price": price,
        "strikethrough_price": strikethrough_price,
        "location": location,
        "listed": listed,
        "description": "",
        "link": f"https://www.facebook.com/marketplace/item/{listing_id}/",
        "image": image,
    }


def _collect_graphql_items(
    page: Any,
    options: SearchOptions,
    url: str,
) -> tuple[dict[str, dict[str, Any]], bool, set[str]]:
    items_by_link: dict[str, dict[str, Any]] = {}
    has_next_page = True
    stable_rounds = 0
    previous_count = 0
    allowed_links: set[str] = set()
    previous_local_links: set[str] = set()

    def handle_marketplace_response(response: Any) -> None:
        nonlocal has_next_page
        try:
            if "facebook.com/api/graphql/" not in str(response.url):
                return
            chunks = _parse_graphql_response_chunks(response.text())
            if not chunks:
                return
            for payload in chunks:
                feed = (((payload.get("data") or {}).get("marketplace_search") or {}).get("feed_units") or {})
                if not feed:
                    continue
                page_info = feed.get("page_info") or {}
                has_next_page = bool(page_info.get("has_next_page"))
                for edge in feed.get("edges") or []:
                    parsed = _listing_from_graphql_edge(edge)
                    if not parsed:
                        continue
                    items_by_link.setdefault(parsed["link"], parsed)
        except Exception:
            return

    page.on("response", handle_marketplace_response)
    try:
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(2_000)
        try:
            page.wait_for_selector('a[href*="/marketplace/item/"]', timeout=12_000)
        except PlaywrightTimeoutError:
            body_text = normalize_text(page.locator("body").inner_text())
            if "log in" in body_text or "inicia sesion" in body_text or "iniciar sesion" in body_text:
                raise RuntimeError(
                    "Facebook pidio sesion valida. Vuelve a guardar storage_state con login completo."
                )
        for _ in range(max(1, options.scroll_limit)):
            if len(items_by_link) == previous_count:
                stable_rounds += 1
            else:
                stable_rounds = 0
            previous_count = len(items_by_link)

            if stable_rounds >= 6 and not has_next_page:
                break

            # Larger scroll + longer wait gives Facebook time to fire GraphQL
            # requests and render the next batch of lazy-loaded cards.
            page.mouse.wheel(0, 4200)
            page.wait_for_timeout(1_800)
            try:
                local_section = page.evaluate(_js_collect_local_section_links())
                local_rows = local_section.get("rows") or []
                current_links = {
                    str(row.get("href") or "").strip()
                    for row in local_rows
                    if str(row.get("href") or "").strip()
                }
                if current_links:
                    allowed_links.update(current_links)
                if local_section.get("cutoff") is None:
                    if current_links:
                        previous_local_links = current_links
                # Bug 2 fix: removed early break when "resultados fuera de busqueda" section
                # is detected. apply_location_radius_filter handles geographic filtering.
            except Exception:
                pass
    finally:
        page.remove_listener("response", handle_marketplace_response)

    if not allowed_links and previous_local_links:
        allowed_links.update(previous_local_links)

    return items_by_link, bool(items_by_link), allowed_links


def _clean_page_lines(raw_text: str) -> list[str]:
    lines: list[str] = []
    seen_empty = False
    for line in str(raw_text or "").splitlines():
        value = " ".join(line.split()).strip()
        if not value:
            if not seen_empty and lines:
                lines.append("")
            seen_empty = True
            continue
        seen_empty = False
        lines.append(value)
    while lines and not lines[-1]:
        lines.pop()
    return lines


def extract_description_from_page_text(
    page_text: str,
    location: str | None,
) -> tuple[str, str]:
    lines = _clean_page_lines(page_text)
    if not lines:
        return "", ""

    stop_markers = {
        "la ubicacion es aproximada",
        "la ubicación es aproximada",
        "informacion del vendedor",
        "información del vendedor",
        "detalles del vendedor",
        "publicidad",
        "envia un mensaje al vendedor",
        "envía un mensaje al vendedor",
        "destacados de hoy",
    }

    start_idx = -1
    condition = ""
    for idx, line in enumerate(lines):
        if normalize_text(line) != "detalles":
            continue
        start_idx = idx + 1
        break

    if start_idx < 0:
        return "", ""

    if start_idx < len(lines) and normalize_text(lines[start_idx]) == "estado":
        start_idx += 1
        if start_idx < len(lines):
            condition = lines[start_idx]
            start_idx += 1

    description_lines: list[str] = []
    normalized_location = normalize_text(location or "")
    for line in lines[start_idx:]:
        normalized = normalize_text(line)
        if normalized in stop_markers:
            break
        if normalized_location and normalized == normalized_location:
            break
        if normalized.startswith("curic") and ", ml" in normalized and normalized_location:
            break
        if normalized.startswith("romeral") and ", ml" in normalized and normalized_location:
            break
        if normalized.startswith("sagrada familia") and ", ml" in normalized and normalized_location:
            break
        if not line:
            if description_lines and description_lines[-1] != "":
                description_lines.append("")
            continue
        description_lines.append(line)

    while description_lines and description_lines[-1] == "":
        description_lines.pop()
    description = "\n".join(description_lines).strip()
    return description, condition


def enrich_items_with_description(
    context: Any,
    items: list[dict[str, Any]],
    timeout_seconds: int,
) -> None:
    if not items:
        return

    page = context.new_page()
    page.set_default_timeout(max(5_000, int(timeout_seconds * 1000)))
    try:
        for item in items:
            try:
                page.goto(item["link"], wait_until="domcontentloaded")
                page.wait_for_timeout(1200)
                body_text = page.locator("body").inner_text()
                description, condition = extract_description_from_page_text(
                    body_text,
                    item.get("location"),
                )
                item["description"] = description
                if condition:
                    item["condition"] = condition
            except Exception:
                item["description"] = item.get("description") or ""
    finally:
        page.close()


def execute_search(options: SearchOptions) -> SearchExecutionResult:
    include_words = options.include_words or []
    exclude_words = options.exclude_words or []
    validate_storage_state(options.storage_state)
    latitude, longitude, resolved_location_label = resolve_search_location(options)
    url = (options.search_url or "").strip() or build_search_url(
        options.query,
        options.marketplace_path,
        options.min_price,
        options.max_price,
        latitude=latitude,
        longitude=longitude,
        radius_km=max(0, options.radius_km),
    )

    playwright = sync_playwright().start()
    context = None
    browser = None
    detach_cleanup = False
    try:
        storage_state = (options.storage_state or "").strip()
        user_data_dir = (options.user_data_dir or "").strip()
        if user_data_dir:
            profile_dir = Path(user_data_dir)
            if not profile_dir.is_absolute():
                profile_dir = ROOT / profile_dir
            profile_dir.mkdir(parents=True, exist_ok=True)
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                channel="chrome",
                headless=not options.show_browser,
                locale="es-CL",
                viewport={"width": 1440, "height": 1080},
            )
            page = context.new_page()
        else:
            browser = playwright.chromium.launch(headless=not options.show_browser)
            context_kwargs: dict[str, Any] = {
                "locale": "es-CL",
                "viewport": {"width": 1440, "height": 1080},
            }
            if storage_state:
                context_kwargs["storage_state"] = storage_state
            context = browser.new_context(**context_kwargs)
            page = context.new_page()

        page.set_default_timeout(max(5_000, int(options.timeout_seconds * 1000)))

        items_by_link, used_graphql, allowed_links = _collect_graphql_items(page, options, url)
        source = "graphql" if used_graphql else "dom"
        if not items_by_link:
            stable_rounds = 0
            previous_count = 0
            for _ in range(max(1, options.scroll_limit)):
                raw_cards = page.evaluate(_js_collect_cards())
                for card in raw_cards:
                    parsed = _parse_card(card)
                    if not parsed:
                        continue
                    items_by_link.setdefault(parsed["link"], parsed)

                if len(items_by_link) == previous_count:
                    stable_rounds += 1
                else:
                    stable_rounds = 0
                previous_count = len(items_by_link)

                if stable_rounds >= 4:
                    break

                page.mouse.wheel(0, 2600)
                page.wait_for_timeout(1200)

        captured_count = len(items_by_link)
        filtered_items = apply_filters(
            list(items_by_link.values()),
            min_price=max(0, options.min_price),
            max_price=max(0, options.max_price),
            word=options.word,
            include_words=include_words,
            exclude_words=exclude_words,
        )

        # Always apply the location radius filter.  The old allowed_links
        # mechanism cross-referenced GraphQL items against DOM links, but
        # the DOM only renders a subset of what GraphQL returns (lazy
        # rendering), so legitimate items were silently dropped.
        all_items = apply_location_radius_filter(
            filtered_items,
            target_latitude=latitude,
            target_longitude=longitude,
            radius_km=max(0, options.radius_km),
            country_code=options.country_code,
            target_city=resolved_location_label,
        )
        total_matches = len(all_items)
        items = all_items[: options.limit]
        if options.include_description:
            enrich_items_with_description(
                context,
                items,
                timeout_seconds=options.timeout_seconds,
            )
        for idx, item in enumerate(items, start=1):
            item["position"] = idx
            if resolved_location_label:
                item["search_location"] = (
                    f"{resolved_location_label} ({max(0, options.radius_km)} km)"
                    if options.radius_km > 0
                    else resolved_location_label
                )
        result = SearchExecutionResult(
            items=items,
            all_items=all_items,
            total_matches=total_matches,
            observed_matches=captured_count,
            source=source,
            filter_breakdown={
                "captured_raw": captured_count,
                "after_text_price_filters": len(filtered_items),
                "after_location_filter": total_matches,
                "search_url": url,
                "resolved_location": resolved_location_label,
                "auth_mode": "user_data_dir" if user_data_dir else ("storage_state" if storage_state else "anonymous"),
            },
        )
        if options.show_browser:
            detach_browser_for_manual_inspection(page, context, browser, playwright)
            detach_cleanup = True
        return result
    finally:
        if not detach_cleanup:
            if context is not None:
                try:
                    context.close()
                except Exception:
                    pass
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass
            try:
                playwright.stop()
            except Exception:
                pass


def collect_results(options: SearchOptions) -> list[dict[str, Any]]:
    return execute_search(options).items


def xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def build_xlsx_bytes(items: list[dict[str, Any]]) -> bytes:
    headers = ["Posicion", "Titulo", "Precio", "Ubicacion", "ZonaBusqueda", "Publicado", "Descripcion", "Link"]
    rows: list[list[str | int]] = [headers]
    for idx, item in enumerate(items, start=1):
        rows.append(
            [
                idx,
                str(item.get("title") or ""),
                str(item.get("price") or ""),
                str(item.get("location") or ""),
                str(item.get("search_location") or ""),
                str(item.get("listed") or ""),
                str(item.get("description") or ""),
                str(item.get("link") or ""),
            ]
        )

    sheet_rows: list[str] = []
    for r_idx, row in enumerate(rows, start=1):
        cells: list[str] = []
        for c_idx, value in enumerate(row, start=1):
            col = ""
            n = c_idx
            while n:
                n, rem = divmod(n - 1, 26)
                col = chr(65 + rem) + col
            ref = f"{col}{r_idx}"
            if isinstance(value, int):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                cells.append(
                    f'<c r="{ref}" t="inlineStr"><is><t>{xml_escape(str(value))}</t></is></c>'
                )
        sheet_rows.append(f"<row r=\"{r_idx}\">{''.join(cells)}</row>")

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(sheet_rows)}</sheetData>"
        "</worksheet>"
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Resultados" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )

    buf = BytesIO()
    with ZipFile(buf, mode="w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return buf.getvalue()


def export_xlsx(items: list[dict[str, Any]], query: str, output_path: str | None) -> Path:
    if output_path and output_path != "__AUTO__":
        out = Path(output_path)
    else:
        safe_query = re.sub(r"[^a-zA-Z0-9_-]+", "_", query)[:40].strip("_") or "busqueda"
        out = ROOT / "exports" / (
            f"facebook_marketplace_{safe_query}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.xlsx"
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(build_xlsx_bytes(items))
    return out


def run(options: SearchOptions, as_json: bool, export_xlsx_path: str | None) -> int:
    items = collect_results(options)

    if export_xlsx_path is not None:
        out = export_xlsx(items, query=options.query, output_path=export_xlsx_path)
        print(f"Excel generado: {out}")
        return 0

    if as_json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return 0

    print(f"Resultados para: {options.query!r} (mostrando {len(items)})\n")
    for item in items:
        print(f"{item['position']}. {item['title']}")
        print(f"   Precio: {item.get('price') or 'N/D'}")
        if item.get("location"):
            print(f"   Ubicacion: {item['location']}")
        if item.get("search_location"):
            print(f"   Zona de busqueda: {item['search_location']}")
        if item.get("listed"):
            print(f"   Publicado: {item['listed']}")
        if item.get("description"):
            print(f"   Descripcion: {item['description'][:180]}")
        print(f"   Link: {item['link']}")
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    started_at = time.perf_counter()
    parser = argparse.ArgumentParser(description="Scraper simple para Facebook Marketplace.")
    parser.add_argument("query", nargs="*", default=["notebook"], help="Termino de busqueda")
    parser.add_argument(
        "--marketplace-path",
        default=DEFAULT_MARKETPLACE_PATH,
        help="Path de Marketplace, ej: curico",
    )
    parser.add_argument("--limit", type=int, default=40, help="Cantidad maxima de resultados")
    parser.add_argument("--scroll-limit", type=int, default=24, help="Cantidad maxima de scrolls")
    parser.add_argument("--min-price", type=int, default=0, help="Precio minimo")
    parser.add_argument("--max-price", type=int, default=0, help="Precio maximo")
    parser.add_argument("--word", default="", help="Palabra obligatoria en el titulo")
    parser.add_argument("--include-word", action="append", default=[], help="Palabra obligatoria adicional")
    parser.add_argument("--exclude-word", action="append", default=[], help="Palabra a descartar")
    parser.add_argument("--include-description", action="store_true", help="Carga descripcion entrando a cada publicacion")
    parser.add_argument("--storage-state", default=None, help="Archivo JSON de storage state de Playwright")
    parser.add_argument(
        "--user-data-dir",
        default=None,
        help="Perfil persistente de Chrome para reutilizar sesion real",
    )
    parser.add_argument("--search-url", default=None, help="URL exacta de Facebook Marketplace")
    parser.add_argument(
        "--location-query",
        default=DEFAULT_LOCATION_QUERY,
        help="Ubicacion de referencia para radio, ej: Curico, Maule, Chile",
    )
    parser.add_argument("--latitude", type=float, default=None, help="Latitud manual")
    parser.add_argument("--longitude", type=float, default=None, help="Longitud manual")
    parser.add_argument("--radius-km", type=int, default=12, help="Radio de busqueda en kilometros")
    parser.add_argument("--country-code", default="CL", help="Codigo pais para geocodificacion")
    parser.add_argument("--show-browser", action="store_true", help="Muestra el navegador")
    parser.add_argument("--timeout-seconds", type=int, default=30, help="Timeout por pagina")
    parser.add_argument("--json", action="store_true", help="Imprime resultados en JSON")
    parser.add_argument("--export-xlsx", nargs="?", const="__AUTO__", default=None, help="Exporta a Excel")
    args = parser.parse_args()

    query = " ".join(args.query).strip()
    if not query and not str(args.search_url or "").strip():
        print("Debes indicar un termino de busqueda o search_url.", file=sys.stderr)
        return 2

    try:
        return run(
            SearchOptions(
                query=query,
                marketplace_path=args.marketplace_path,
                limit=max(1, args.limit),
                scroll_limit=max(1, args.scroll_limit),
                min_price=max(0, args.min_price),
                max_price=max(0, args.max_price),
                word=args.word,
                include_words=args.include_word,
                exclude_words=args.exclude_word,
                include_description=bool(args.include_description),
                storage_state=args.storage_state,
                user_data_dir=args.user_data_dir,
                search_url=args.search_url,
                location_query=args.location_query,
                latitude=args.latitude,
                longitude=args.longitude,
                radius_km=max(0, args.radius_km),
                country_code=args.country_code,
                show_browser=bool(args.show_browser),
                timeout_seconds=max(5, args.timeout_seconds),
            ),
            as_json=bool(args.json),
            export_xlsx_path=args.export_xlsx,
        )
    except Exception as exc:
        print(f"Error al obtener datos de Facebook Marketplace: {exc}", file=sys.stderr)
        return 1
    finally:
        elapsed = time.perf_counter() - started_at
        print(f"Tiempo total: {elapsed:.2f}s", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())

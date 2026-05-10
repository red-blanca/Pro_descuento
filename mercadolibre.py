from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import http.client
import json
import os
import re
import socket
import sys
import time
import unicodedata
import math
from datetime import datetime
from html import unescape
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import quote, quote_plus, unquote, urljoin
from urllib.request import HTTPCookieProcessor, Request, build_opener
from urllib.error import HTTPError, URLError
from zipfile import ZIP_DEFLATED, ZipFile
import http.cookiejar

DOMAIN_BY_COUNTRY = {
    "ar": "mercadolibre.com.ar",
    "cl": "mercadolibre.cl",
    "mx": "mercadolibre.com.mx",
    "co": "mercadolibre.com.co",
    "pe": "mercadolibre.com.pe",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

LOCAL_SHIPPING_FILTER = "SHIPPING*ORIGIN_10215068"
CONDITION_TOKEN_BY_FILTER = {
    "new": "ITEM*CONDITION_2230284",
    "used": "ITEM*CONDITION_2230581",
    "reconditioned": "ITEM*CONDITION_2234833",
}
DEFAULT_PAGE_SIZE = 48
MAX_EMPTY_PAGES = 5
REQUEST_RETRIES = 4
REQUEST_COOKIE_HEADER: str | None = None
ROOT = Path(__file__).resolve().parent
PAGE_CACHE_TTL_SECONDS = 300
PAGE_CACHE: dict[str, tuple[float, str]] = {}
MAX_WORKERS = 5


def _progress(prefix: str, current: int, total: int | None = None) -> None:
    if total and total > 0:
        pct = min(100, int((current / total) * 100))
        bar_w = 24
        filled = int((pct / 100) * bar_w)
        bar = "#" * filled + "-" * (bar_w - filled)
        msg = f"\r{prefix} [{bar}] {pct:3d}% ({current}/{total})"
    else:
        msg = f"\r{prefix} {current}"
    print(msg, end="", file=sys.stderr, flush=True)


def _progress_done() -> None:
    print(file=sys.stderr, flush=True)


def clean_html_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return unescape(text).strip()


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    no_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return no_accents.lower().strip()


def text_has_term(text: str, term: str, whole_word: bool = False) -> bool:
    term = term.strip()
    if not term:
        return False
    if not whole_word:
        return term in text
    
    # Match as whole word using regex
    # We use a simple \b boundary but escape the term
    pattern = rf"\b{re.escape(term)}\b"
    return bool(re.search(pattern, text, re.IGNORECASE))


def extract_price_from_block(block: str) -> str | None:
    current_match = re.search(
        r'<div class="poly-price__current".*?</div>', block, flags=re.DOTALL
    )
    search_scope = current_match.group(0) if current_match else block

    fraction = re.search(
        r'data-andes-money-amount-fraction="true">([^<]+)</span>', search_scope
    )
    if fraction:
        value = clean_html_text(fraction.group(1))
        return f"$ {value}" if value else None

    aria = re.search(r'aria-label="((?!Antes:)[^\"]+)"', search_scope)
    if aria:
        return clean_html_text(aria.group(1))

    return None


def extract_image_from_block(block: str) -> str | None:
    image_match = re.search(r'<img[^>]+class="[^"]*poly-component__picture[^"]*"[^>]+>', block)
    if not image_match:
        return None

    tag = image_match.group(0)
    src_match = re.search(r'\ssrc="([^"]+)"', tag)
    if not src_match:
        src_match = re.search(r'\sdata-src="([^"]+)"', tag)
    if not src_match:
        return None

    return unescape(src_match.group(1))


def extract_discount_percent_from_block(block: str) -> int | None:
    patterns = [
        r'(\d{1,3})\s*%\s*OFF',
        r'(\d{1,3})\s*%\s*dcto',
        r'(\d{1,3})\s*%\s*de\s*descuento',
        r'andes-money-amount-discount[^>]*>\s*(\d{1,3})\s*%',
        r'poly-price__discount[^>]*>\s*(\d{1,3})\s*%',
    ]
    for pattern in patterns:
        match = re.search(pattern, block, flags=re.IGNORECASE)
        if not match:
            continue
        try:
            value = int(match.group(1))
        except ValueError:
            continue
        if 0 <= value <= 100:
            return value
    return None


def extract_condition_from_block(block: str) -> str | None:
    text = clean_html_text(block).lower()
    if "reacondicion" in text:
        return "reconditioned"
    if "usado" in text:
        return "used"
    if "nuevo con caja abierta" in text:
        return "new"
    if "nuevo" in text:
        return "new"
    return None


def _build_opener() -> tuple[Any, http.cookiejar.CookieJar]:
    jar = http.cookiejar.CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar))
    return opener, jar


def _read_html(opener: Any, url: str, timeout: int) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": "https://www.google.com/",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1"
    }
    if REQUEST_COOKIE_HEADER:
        headers["Cookie"] = REQUEST_COOKIE_HEADER
    req = Request(url, headers=headers)
    with opener.open(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def _cache_get_html(url: str) -> str | None:
    entry = PAGE_CACHE.get(url)
    if not entry:
        return None
    expires_at, html = entry
    if expires_at < time.time():
        PAGE_CACHE.pop(url, None)
        return None
    return html


def _cache_set_html(url: str, html: str) -> None:
    PAGE_CACHE[url] = (time.time() + PAGE_CACHE_TTL_SECONDS, html)


def _is_transient_network_error(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, socket.timeout, ConnectionError, http.client.RemoteDisconnected)):
        return True
    if isinstance(exc, HTTPError):
        return exc.code in {408, 429, 500, 502, 503, 504}
    if isinstance(exc, URLError):
        return True
    return False


def _sleep_before_retry(attempt: int) -> None:
    time.sleep(min(0.8 * (2 ** attempt), 6.0))


def _parse_cookie_pairs(raw: str) -> str:
    parts = []
    for token in raw.split(";"):
        token = token.strip()
        if not token or "=" not in token:
            continue
        name, value = token.split("=", 1)
        name = name.strip()
        value = value.strip()
        if name:
            parts.append(f"{name}={value}")
    return "; ".join(parts)


def configure_cookie_header(cookie_inline: str | None, cookie_file: str | None) -> None:
    global REQUEST_COOKIE_HEADER
    env_cookie = os.getenv("ML_COOKIE", "").lstrip("\ufeff").strip()
    content = ""
    if cookie_file:
        cookie_path = Path(cookie_file)
        if not cookie_path.is_absolute():
            cookie_path = ROOT / cookie_path
        if cookie_path.exists():
            content = cookie_path.read_text(encoding="utf-8").lstrip("\ufeff").strip()
        elif env_cookie:
            content = env_cookie
        else:
            raise FileNotFoundError(f"No existe el archivo de cookies: {cookie_path}")
    elif cookie_inline:
        content = cookie_inline.lstrip("\ufeff").strip()
    elif env_cookie:
        content = env_cookie
    REQUEST_COOKIE_HEADER = _parse_cookie_pairs(content) if content else None


def fetch_url_html(url: str, timeout: int = 20) -> str:
    cached = _cache_get_html(url)
    if cached is not None:
        return cached
    last_exc: BaseException | None = None
    for attempt in range(REQUEST_RETRIES):
        opener, _ = _build_opener()
        try:
            html = _read_html(opener, url, timeout)
            _cache_set_html(url, html)
            return html
        except BaseException as exc:
            last_exc = exc
            if not _is_transient_network_error(exc) or attempt >= REQUEST_RETRIES - 1:
                raise
            _sleep_before_retry(attempt)
    if last_exc:
        raise last_exc
    raise RuntimeError("No se pudo leer MercadoLibre.")


def _solve_bm_challenge(cookie_jar: http.cookiejar.CookieJar, domain: str) -> bool:
    bm_cookie = next((c for c in cookie_jar if c.name == "_bmstate"), None)
    if not bm_cookie:
        return False

    decoded = unquote(bm_cookie.value)
    parts = decoded.split(";")
    if len(parts) < 2:
        return False

    token = parts[0]
    try:
        difficulty = int(parts[1])
    except ValueError:
        return False

    prefix = "0" * difficulty
    nonce = 0

    while nonce < 2_000_000:
        digest = hashlib.sha256(f"{token}{nonce}".encode("utf-8")).hexdigest()
        if digest.startswith(prefix):
            break
        nonce += 1
    else:
        return False

    value = quote(f"{token};{nonce}", safe="")
    challenge_cookie = http.cookiejar.Cookie(
        version=0,
        name="_bmc",
        value=value,
        port=None,
        port_specified=False,
        domain=f".{domain}",
        domain_specified=True,
        domain_initial_dot=True,
        path="/",
        path_specified=True,
        secure=False,
        expires=int(time.time()) + 86_000,
        discard=False,
        comment=None,
        comment_url=None,
        rest={},
        rfc2109=False,
    )
    cookie_jar.set_cookie(challenge_cookie)
    return True


def build_search_url(query: str, country: str, exclude_international: bool = True) -> str:
    domain = DOMAIN_BY_COUNTRY[country]
    slug = quote_plus(query.strip()).replace("+", "-")
    url = f"https://listado.{domain}/{slug}"
    if exclude_international:
        return f"{url}_NoIndex_True_{LOCAL_SHIPPING_FILTER}"
    return f"{url}_NoIndex_True"


def build_filter_tokens(
    min_price: int,
    max_price: int,
    min_discount: int,
    sort_price: bool,
    exclude_international: bool,
    condition_filter: str,
) -> list[str]:
    tokens: list[str] = []
    if sort_price:
        tokens.append("OrderId_PRICE")
    if min_price > 0 or max_price > 0:
        low = max(0, min_price)
        high = max_price if max_price > 0 else 999999999
        if high < low:
            low, high = high, low
        tokens.append(f"PriceRange_{low}-{high}")
    if min_discount > 0:
        tokens.append(f"Discount_{max(1, min(min_discount, 100))}-100")
    condition_token = CONDITION_TOKEN_BY_FILTER.get(condition_filter)
    if condition_token:
        tokens.append(condition_token)
    tokens.append("NoIndex_True")
    if exclude_international:
        tokens.append(LOCAL_SHIPPING_FILTER)
    return tokens


def append_filter_tokens(base_url: str, tokens: list[str]) -> str:
    if not tokens:
        return base_url
    return f"{base_url}_{'_'.join(tokens)}"


def insert_start_in_url(url: str, start: int) -> str:
    if start <= 1 or f"_Desde_{start}" in url:
        return url
    url = re.sub(r"_Desde_\d+", "", url)
    marker_positions = [
        pos for marker in ("_OrderId_", "_PriceRange_", "_Discount_", "_ITEM*", "_NoIndex_", "_SHIPPING*")
        if (pos := url.find(marker)) >= 0
    ]
    if marker_positions:
        pos = min(marker_positions)
        return f"{url[:pos]}_Desde_{start}{url[pos:]}"
    hash_pos = url.find("#")
    if hash_pos >= 0:
        return f"{url[:hash_pos]}_Desde_{start}{url[hash_pos:]}"
    return f"{url}_Desde_{start}"


def set_price_range_in_url(url: str, min_price: int, max_price: int) -> str:
    main, sep, fragment = url.partition("#")
    main = re.sub(r"_Desde_\d+", "", main)
    main = re.sub(r"_PriceRange_\d+-\d+", "", main)
    token = f"_PriceRange_{max(0, min_price)}-{max(0, max_price)}"
    marker_positions = [
        pos for marker in ("_NoIndex_", "_SHIPPING*", "_Discount_", "_ITEM*")
        if (pos := main.find(marker)) >= 0
    ]
    if marker_positions:
        pos = min(marker_positions)
        main = f"{main[:pos]}{token}{main[pos:]}"
    else:
        main = f"{main}{token}"
    return f"{main}{sep}{fragment}" if sep else main


def build_search_url_with_start(
    query: str,
    country: str,
    start: int,
    exclude_international: bool = True,
    min_price: int = 0,
    max_price: int = 0,
    min_discount: int = 0,
    sort_price: bool = False,
    condition_filter: str = "any",
    category_alias: str | None = None,
) -> str:
    domain = DOMAIN_BY_COUNTRY[country]
    slug = quote_plus(query.strip()).replace("+", "-")
    if category_alias and category_alias.strip():
        cat = category_alias.strip()
        if slug:
            base = f"https://listado.{domain}/{cat}/{slug}"
        else:
            base = f"https://listado.{domain}/{cat}"
    else:
        if slug:
            base = f"https://listado.{domain}/{slug}"
        else:
            base = f"https://listado.{domain}/ofertas"
    if start > 1:
        base = f"{base}_Desde_{start}"
    return append_filter_tokens(
        base,
        build_filter_tokens(
            min_price, max_price, min_discount, sort_price, exclude_international, condition_filter
        ),
    )


def build_search_url_with_category(
    query: str,
    country: str,
    start: int,
    exclude_international: bool = True,
    min_price: int = 0,
    max_price: int = 0,
    min_discount: int = 0,
    sort_price: bool = False,
    condition_filter: str = "any",
) -> str:
    domain = DOMAIN_BY_COUNTRY[country]
    slug = quote_plus(query.strip()).replace("+", "-")
    base = f"https://listado.{domain}/_CustId_0_{slug}"
    if start > 1:
        base = f"{base}_Desde_{start}"
    return append_filter_tokens(
        base,
        build_filter_tokens(
            min_price, max_price, min_discount, sort_price, exclude_international, condition_filter
        ),
    )


def looks_like_results_page(html: str) -> bool:
    return (
        "poly-component__title" in html
        or "ui-search-layout" in html
        or "poly-card__content" in html
    )


def looks_like_traffic_block(html: str) -> bool:
    text = html.lower()
    return (
        "suspicious-traffic-frontend" in text
        or "account-verification" in text
        or "tráfico sospechoso" in text
        or "trafico sospechoso" in text
        or "verifica que eres" in text
    )


def _raise_traffic_block() -> None:
    raise RuntimeError(
        "Mercado Libre está mostrando una verificación de tráfico sospechoso para esta sesión/IP. "
        "Abre Mercado Libre en tu navegador, resuelve la verificación si aparece y exporta cookies "
        "actualizadas a cookies.txt, o reintenta más tarde desde otra red."
    )


def fetch_search_page_html(
    query: str, country: str, timeout: int = 20, exclude_international: bool = True
) -> str:
    url = build_search_url(query, country, exclude_international=exclude_international)
    domain = DOMAIN_BY_COUNTRY[country]

    opener, jar = _build_opener()
    html = _read_html(opener, url, timeout)
    if looks_like_traffic_block(html):
        _raise_traffic_block()

    if "This page requires JavaScript to work" not in html:
        return html

    if not _solve_bm_challenge(jar, domain):
        raise RuntimeError("Bloqueado por anti-bot y no se pudo resolver el desafío.")

    html = _read_html(opener, url, timeout)
    if looks_like_traffic_block(html):
        _raise_traffic_block()
    if "This page requires JavaScript to work" in html:
        raise RuntimeError("Bloqueado por anti-bot después de reintentar.")

    return html


def extract_nordic_context(html: str) -> dict[str, Any]:
    marker = "_n.ctx.r="
    pos = html.find(marker)
    if pos < 0:
        return {}
    decoder = json.JSONDecoder()
    try:
        obj, _ = decoder.raw_decode(html[pos + len(marker):])
        return obj if isinstance(obj, dict) else {}
    except json.JSONDecodeError:
        return {}


def _normalize_polycard_to_result(polycard_entry: dict[str, Any], url_prefix: str = "https://", country: str = "cl") -> dict[str, Any] | None:
    """Convert a polycard result entry into the legacy search_api result format."""
    poly = polycard_entry.get("polycard")
    if not isinstance(poly, dict):
        return None

    meta = poly.get("metadata", {})
    comps = poly.get("components", [])
    pics = poly.get("pictures", [])
    item_id = meta.get("id", "")

    if not item_id or not item_id.startswith("MLC"):
        return None

    # Skip ads (is_pad items have tracking URLs, not direct product links)
    # We still extract them but mark them; downstream can filter if needed

    title = ""
    price_value = None
    original_price_value = None
    discount_pct = None
    condition_text = ""

    for c in comps:
        if not isinstance(c, dict):
            continue
        ctype = c.get("type", "")
        if ctype == "title":
            td = c.get("title", {})
            title = td.get("text", "") if isinstance(td, dict) else str(td or "")
        elif ctype == "price":
            pd = c.get("price", {})
            if isinstance(pd, dict):
                cp = pd.get("current_price", {})
                if isinstance(cp, dict):
                    price_value = cp.get("value")
                op = pd.get("original_price", {})
                if isinstance(op, dict):
                    original_price_value = op.get("value")
                disc = pd.get("discount", {})
                if isinstance(disc, dict):
                    discount_pct = disc.get("value")
        elif ctype == "highlight":
            hl = c.get("highlight", {})
            if isinstance(hl, dict):
                label = hl.get("label", {})
                if isinstance(label, dict):
                    hl_text = str(label.get("text", "")).lower()
                    if "reacondicion" in hl_text:
                        condition_text = "refurbished"
                    elif "usado" in hl_text:
                        condition_text = "used"

    # Build permalink
    domain = DOMAIN_BY_COUNTRY.get(country, "mercadolibre.cl")
    permalink = f"https://articulo.{domain}/{item_id}"

    # Extract thumbnail from pictures
    thumbnail = ""
    if isinstance(pics, dict):
        # New polycard format: pics = {pictures: [{id: "..."}], square: "Q", ...}
        pic_list = pics.get("pictures", [])
        square = pics.get("square", "Q")
        if pic_list and isinstance(pic_list, list):
            p0 = pic_list[0]
            if isinstance(p0, dict) and p0.get("id"):
                pic_id = p0["id"]
                thumbnail = f"https://http2.mlstatic.com/D_{square}_NP_{pic_id}-E.webp"
    elif isinstance(pics, list) and pics:
        p0 = pics[0]
        if isinstance(p0, dict):
            thumbnail = str(p0.get("url", "") or p0.get("src", "") or "")
        elif isinstance(p0, str):
            thumbnail = p0

    # Calculate discount if not provided
    if discount_pct is None and price_value and original_price_value:
        try:
            if float(original_price_value) > float(price_value):
                discount_pct = round(((float(original_price_value) - float(price_value)) / float(original_price_value)) * 100)
        except (TypeError, ValueError):
            pass

    return {
        "id": item_id,
        "title": title,
        "price": price_value,
        "original_price": original_price_value,
        "permalink": permalink,
        "thumbnail": thumbnail,
        "condition": condition_text or None,
        "discount_percent": discount_pct,
        "is_pad": meta.get("is_pad") == "true",
    }


def _extract_polycard_search_api(ctx: dict[str, Any], country: str = "cl") -> dict[str, Any]:
    """Extract search data from the new polycard-based HTML structure and
    return it in a format compatible with the legacy search_api dict."""
    app = ctx.get("appProps", {})

    # Try multiple paths to find initialState
    init_state = None
    for init_path in [
        (app, "pageProps", "initialState"),
        (app, "sharedState", "search"),
    ]:
        node = init_path[0]
        for key in init_path[1:]:
            if isinstance(node, dict):
                node = node.get(key, {})
            else:
                node = {}
                break
        if isinstance(node, dict) and node.get("results"):
            init_state = node
            break

    if not init_state:
        return {}

    raw_results = init_state.get("results", [])
    if not raw_results:
        return {}

    # Get polycard context for URL prefix
    poly_ctx = init_state.get("polycard_context", {})
    url_prefix = poly_ctx.get("url_prefix", "https://")

    # Normalize polycards into legacy result format
    results = []
    for entry in raw_results:
        if not isinstance(entry, dict):
            continue
        # Skip non-polycard entries (filters, interventions, etc.)
        if entry.get("id") != "POLYCARD":
            continue
        normalized = _normalize_polycard_to_result(entry, url_prefix, country)
        if normalized and normalized.get("title"):
            results.append(normalized)

    if not results:
        return {}

    # Extract pagination info
    pag = init_state.get("pagination", {})
    page_count = int(pag.get("page_count") or 0)
    results_limit = int(pag.get("results_limit") or 2000)
    page_size = len(results)

    # Get total from melidata or estimate from pagination
    meli = init_state.get("melidata_track", {})
    event_data = meli.get("event_data", {}) if isinstance(meli, dict) else {}
    total = event_data.get("total_results")
    if not total:
        total = page_count * page_size if page_count else len(results)

    # Build pagination URLs list for multi-page fetching
    pagination_urls = []
    pag_nodes = pag.get("pagination_nodes_url", [])
    for node in pag_nodes:
        if isinstance(node, dict) and node.get("url"):
            pagination_urls.append(node["url"])

    return {
        "results": results,
        "paging": {
            "total": int(total or len(results)),
            "primary_results": min(int(total or 0), results_limit),
            "offset": 0,
            "limit": page_size,
        },
        "available_filters": [],
        "filters": [],
        "_pagination_urls": pagination_urls,
        "_polycard_format": True,
    }


def extract_search_api_from_html(html: str, country: str = "cl") -> dict[str, Any]:
    ctx = extract_nordic_context(html)

    # Try legacy paths first (search_api inside pagination)
    paths = [
        ("appProps", "pageProps", "initialState", "pagination", "search_api"),
        ("appProps", "sharedState", "search", "pagination", "search_api"),
        ("appProps", "sharedState", "locationSearch", "initialState", "pagination", "search_api"),
    ]
    for path in paths:
        node: Any = ctx
        for key in path:
            if not isinstance(node, dict):
                node = None
                break
            node = node.get(key)
        if isinstance(node, dict) and node.get("results"):
            return node

    # Fallback: extract from new polycard-based structure
    polycard_api = _extract_polycard_search_api(ctx, country)
    if polycard_api:
        return polycard_api

    return {}


def search_metadata_from_url(url: str, country: str, timeout: int = 20) -> dict[str, Any]:
    html = fetch_url_html(url, timeout=timeout)
    if looks_like_traffic_block(html):
        _raise_traffic_block()
    search_api = extract_search_api_from_html(html, country=country)
    if not search_api:
        opener, jar = _build_opener()
        html = fetch_page_with_challenge(opener, jar, url, country, timeout=timeout)
        search_api = extract_search_api_from_html(html, country=country)
    return search_api


def _attribute_value(result: dict[str, Any], attr_id: str) -> str:
    for attr in result.get("attributes") or []:
        if str(attr.get("id") or "") == attr_id:
            return str(attr.get("value_name") or attr.get("value_id") or "")
    return ""


def _condition_from_result(result: dict[str, Any]) -> str | None:
    raw = " ".join([
        _attribute_value(result, "ITEM_CONDITION"),
        str(result.get("condition") or ""),
    ]).lower()
    if "reacondicion" in raw or "refurbished" in raw:
        return "reconditioned"
    if "usado" in raw or "used" in raw:
        return "used"
    if "nuevo" in raw or "new" in raw:
        return "new"
    return None


def _format_price_from_result(result: dict[str, Any]) -> str:
    price = result.get("price") or result.get("current_price")
    if isinstance(price, dict):
        price = (
            price.get("amount")
            or price.get("value")
            or price.get("fraction")
            or price.get("cents")
        )
    if price is None:
        return ""
    try:
        amount = int(float(price))
        return f"$ {amount:,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(price)


def normalize_result_from_search_api(result: dict[str, Any]) -> dict[str, Any]:
    winner = result.get("buy_box_winner") if isinstance(result.get("buy_box_winner"), dict) else {}
    offer = {**result, **winner}
    link = str(offer.get("permalink") or offer.get("url") or offer.get("link") or "")
    image = str(offer.get("thumbnail") or offer.get("image") or "")
    pictures = offer.get("pictures") or result.get("pictures") or []
    if not image and pictures and isinstance(pictures[0], dict):
        image = str(pictures[0].get("url") or "")
    images = result.get("images") or []
    if not image and images and isinstance(images[0], dict):
        image = str(images[0].get("url") or images[0].get("secure_url") or "")
    discount = offer.get("discount_percent") or offer.get("discount_rate")
    if discount is None:
        price = offer.get("price")
        original = offer.get("original_price")
        if isinstance(price, dict):
            price = price.get("amount") or price.get("value")
        if isinstance(original, dict):
            original = original.get("amount") or original.get("value")
        try:
            if original and price and float(original) > float(price):
                discount = round(((float(original) - float(price)) / float(original)) * 100)
        except (TypeError, ValueError):
            discount = None
    return {
        "position": 0,
        "title": str(offer.get("title") or offer.get("name") or result.get("title") or result.get("name") or ""),
        "price": _format_price_from_result(offer),
        "link": link,
        "image": image,
        "discount_percent": int(discount) if isinstance(discount, (int, float)) else None,
        "condition": _condition_from_result(offer) or _condition_from_result(result),
    }


def _paging_int(search_api: dict[str, Any], key: str) -> int:
    try:
        return int((search_api.get("paging") or {}).get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _collect_results_from_listing_url(
    first_url: str,
    country: str,
    limit: int,
    fetch_all: bool,
    max_pages: int,
    timeout: int,
    first_api: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    first_api = first_api or search_metadata_from_url(first_url, country, timeout=timeout)
    paging = first_api.get("paging") or {}
    page_limit = int(paging.get("limit") or DEFAULT_PAGE_SIZE)
    total = int(paging.get("total") or 0)
    primary_results = int(paging.get("primary_results") or total or 0)
    accessible_total = min(total, primary_results) if primary_results > 0 and total > 0 else (primary_results or total)
    if not fetch_all:
        target_items = max(1, limit)
    else:
        target_items = accessible_total or limit
    target_pages = max(1, math.ceil(target_items / max(1, page_limit)))
    if max_pages > 0:
        target_pages = min(target_pages, max_pages)

    starts = [1 + (page_limit * idx) for idx in range(target_pages)]
    urls = [first_url] + [insert_start_in_url(first_url, start) for start in starts[1:]]
    pages: dict[int, dict[str, Any]] = {0: first_api}

    def fetch_idx(idx_url: tuple[int, str]) -> tuple[int, dict[str, Any]]:
        idx, url = idx_url
        return idx, search_metadata_from_url(url, country, timeout=timeout)

    if len(urls) > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(urls) - 1)) as executor:
            futures = [executor.submit(fetch_idx, item) for item in enumerate(urls[1:], start=1)]
            for future in concurrent.futures.as_completed(futures):
                try:
                    idx, api = future.result()
                except HTTPError as exc:
                    if exc.code == 404:
                        continue
                    raise
                pages[idx] = api

    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    fetched_raw = 0
    for idx in sorted(pages):
        results = pages[idx].get("results") or []
        fetched_raw += len(results)
        for raw in results:
            item = normalize_result_from_search_api(raw)
            link_key = item.get("link") or item.get("title")
            if not link_key or link_key in seen:
                continue
            seen.add(str(link_key))
            item["position"] = len(items) + 1
            items.append(item)
            if len(items) >= limit:
                break
        if len(items) >= limit:
            break

    meta = {
        "total": total,
        "primary_results": primary_results,
        "accessible_total": accessible_total,
        "page_limit": page_limit,
        "pages_fetched": len(pages),
        "fetched_raw": fetched_raw,
        "search_url": first_url,
        "available_filters": first_api.get("available_filters") or [],
        "filters": first_api.get("filters") or [],
    }
    return items, meta


def _collect_results_split_by_price(
    first_url: str,
    country: str,
    limit: int,
    max_pages: int,
    min_price: int,
    max_price: int,
    timeout: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    lower = max(0, min_price)
    upper = max_price if max_price > 0 else 999_999_999
    seed_ranges: list[tuple[int, int]] = []
    for start in range(0, 100_000, 10_000):
        seed_ranges.append((start, start + 9_999))
    seed_ranges.extend([
        (100_000, 149_999),
        (150_000, 199_999),
        (200_000, 249_999),
        (250_000, 299_999),
        (300_000, 399_999),
        (400_000, 599_999),
        (600_000, 999_999),
        (1_000_000, 1_999_999),
        (2_000_000, 999_999_999),
    ])

    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    pages_fetched = 0
    fetched_raw = 0
    split_ranges: list[dict[str, int]] = []
    total_reported = 0
    page_budget = max_pages if max_pages > 0 else 0

    for seed_low, seed_high in seed_ranges:
        low = max(lower, seed_low)
        high = min(upper, seed_high)
        if low > high:
            continue
        if len(items) >= limit or (page_budget and page_budget <= 0):
            break
        remaining = limit - len(items)
        bucket_pages = page_budget if page_budget else 0
        try:
            bucket_items, bucket_meta = _collect_results_from_listing_url(
                set_price_range_in_url(first_url, low, high), country, remaining, True, bucket_pages, timeout
            )
        except HTTPError as exc:
            if exc.code == 404:
                continue
            raise
        range_total = int(bucket_meta.get("total") or 0)
        if range_total <= 0 and not bucket_items:
            continue
        total_reported += range_total
        pages_fetched += int(bucket_meta.get("pages_fetched") or 0)
        fetched_raw += int(bucket_meta.get("fetched_raw") or 0)
        if page_budget:
            page_budget -= int(bucket_meta.get("pages_fetched") or 0)
        split_ranges.append({"min": low, "max": high, "total": range_total})
        for item in bucket_items:
            link_key = str(item.get("link") or item.get("title") or "")
            if not link_key or link_key in seen:
                continue
            seen.add(link_key)
            item["position"] = len(items) + 1
            items.append(item)
            if len(items) >= limit:
                break

    return items, {
        "total": total_reported,
        "primary_results": 0,
        "accessible_total": total_reported,
        "page_limit": DEFAULT_PAGE_SIZE,
        "pages_fetched": pages_fetched,
        "fetched_raw": fetched_raw,
        "search_url": first_url,
        "available_filters": [],
        "filters": [],
        "split_by_price": True,
        "split_ranges": split_ranges,
    }


def collect_results_from_search_api(
    query: str,
    country: str,
    limit: int,
    fetch_all: bool,
    max_pages: int,
    exclude_international: bool,
    min_price: int,
    max_price: int,
    min_discount: int,
    sort_price: bool,
    condition_filter: str,
    search_url: str | None = None,
    category_url: str | None = None,
    timeout: int = 20,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    first_url = build_initial_listing_url(
        query, country, exclude_international, min_price, max_price, min_discount,
        sort_price, condition_filter, search_url=search_url, category_url=category_url,
    )
    first_api = search_metadata_from_url(first_url, country, timeout=timeout)
    total = _paging_int(first_api, "total")
    primary_results = _paging_int(first_api, "primary_results") or total
    accessible_total = min(total, primary_results) if primary_results > 0 and total > 0 else (primary_results or total)
    if fetch_all and total > accessible_total and limit > accessible_total:
        items, meta = _collect_results_split_by_price(
            first_url, country, limit, max_pages, min_price, max_price, timeout
        )
        meta["split_covered_total"] = meta.get("total", 0)
        meta["total"] = total
        meta["primary_results"] = primary_results
        return items, meta
    return _collect_results_from_listing_url(
        first_url, country, limit, fetch_all, max_pages, timeout, first_api=first_api
    )


def build_initial_listing_url(
    query: str,
    country: str,
    exclude_international: bool,
    min_price: int,
    max_price: int,
    min_discount: int,
    sort_price: bool,
    condition_filter: str,
    search_url: str | None = None,
    category_url: str | None = None,
) -> str:
    if search_url and search_url.strip():
        return search_url.strip()
    if category_url and category_url.strip() and category_url.strip().startswith("http"):
        return category_url.strip()
        
    cat_alias = category_url.strip() if category_url and category_url.strip() else None

    return build_search_url_with_start(
        query,
        country,
        1,
        exclude_international=exclude_international,
        min_price=min_price,
        max_price=max_price,
        min_discount=min_discount,
        sort_price=sort_price,
        condition_filter=condition_filter,
        category_alias=cat_alias,
    )


def build_search_url_with_category(
    query: str,
    country: str,
    start: int,
    exclude_international: bool = True,
    min_price: int = 0,
    max_price: int = 0,
    min_discount: int = 0,
    sort_price: bool = False,
    condition_filter: str = "any",
) -> str:
    domain = DOMAIN_BY_COUNTRY[country]
    slug = quote_plus(query.strip()).replace("+", "-")
    base = f"https://listado.{domain}/_CustId_0_{slug}"
    if start > 1:
        base = f"{base}_Desde_{start}"
    return append_filter_tokens(
        base,
        build_filter_tokens(
            min_price, max_price, min_discount, sort_price, exclude_international, condition_filter
        ),
    )


def looks_like_results_page(html: str) -> bool:
    return (
        "poly-component__title" in html
        or "ui-search-layout" in html
        or "poly-card__content" in html
    )


def looks_like_traffic_block(html: str) -> bool:
    text = html.lower()
    return (
        "suspicious-traffic-frontend" in text
        or "account-verification" in text
        or "tráfico sospechoso" in text
        or "trafico sospechoso" in text
        or "verifica que eres" in text
    )


def _raise_traffic_block() -> None:
    raise RuntimeError(
        "Mercado Libre está mostrando una verificación de tráfico sospechoso para esta sesión/IP. "
        "Abre Mercado Libre en tu navegador, resuelve la verificación si aparece y exporta cookies "
        "actualizadas a cookies.txt, o reintenta más tarde desde otra red."
    )


def fetch_search_page_html(
    query: str, country: str, timeout: int = 20, exclude_international: bool = True
) -> str:
    url = build_search_url(query, country, exclude_international=exclude_international)
    domain = DOMAIN_BY_COUNTRY[country]

    opener, jar = _build_opener()
    html = _read_html(opener, url, timeout)
    if looks_like_traffic_block(html):
        _raise_traffic_block()

    if "This page requires JavaScript to work" not in html:
        return html

    if not _solve_bm_challenge(jar, domain):
        raise RuntimeError("Bloqueado por anti-bot y no se pudo resolver el desafío.")

    html = _read_html(opener, url, timeout)
    if looks_like_traffic_block(html):
        _raise_traffic_block()
    if "This page requires JavaScript to work" in html:
        raise RuntimeError("Bloqueado por anti-bot después de reintentar.")

    return html


def extract_nordic_context(html: str) -> dict[str, Any]:
    marker = "_n.ctx.r="
    pos = html.find(marker)
    if pos < 0:
        return {}
    decoder = json.JSONDecoder()
    try:
        obj, _ = decoder.raw_decode(html[pos + len(marker):])
        return obj if isinstance(obj, dict) else {}
    except json.JSONDecodeError:
        return {}


def extract_search_api_from_html(html: str, country: str = "cl") -> dict[str, Any]:
    ctx = extract_nordic_context(html)

    # Try legacy paths first (search_api inside pagination)
    paths = [
        ("appProps", "pageProps", "initialState", "pagination", "search_api"),
        ("appProps", "sharedState", "search", "pagination", "search_api"),
        ("appProps", "sharedState", "locationSearch", "initialState", "pagination", "search_api"),
    ]
    for path in paths:
        node: Any = ctx
        for key in path:
            if not isinstance(node, dict):
                node = None
                break
            node = node.get(key)
        if isinstance(node, dict) and node.get("results"):
            return node

    # Fallback: extract from new polycard-based structure
    polycard_api = _extract_polycard_search_api(ctx, country)
    if polycard_api:
        return polycard_api

    return {}


def search_metadata_from_url(url: str, country: str, timeout: int = 20) -> dict[str, Any]:
    html = fetch_url_html(url, timeout=timeout)
    if looks_like_traffic_block(html):
        _raise_traffic_block()
    search_api = extract_search_api_from_html(html, country=country)
    if not search_api:
        opener, jar = _build_opener()
        html = fetch_page_with_challenge(opener, jar, url, country, timeout=timeout)
        search_api = extract_search_api_from_html(html, country=country)
    return search_api


def _attribute_value(result: dict[str, Any], attr_id: str) -> str:
    for attr in result.get("attributes") or []:
        if str(attr.get("id") or "") == attr_id:
            return str(attr.get("value_name") or attr.get("value_id") or "")
    return ""


def _condition_from_result(result: dict[str, Any]) -> str | None:
    raw = " ".join([
        _attribute_value(result, "ITEM_CONDITION"),
        str(result.get("condition") or ""),
    ]).lower()
    if "reacondicion" in raw or "refurbished" in raw:
        return "reconditioned"
    if "usado" in raw or "used" in raw:
        return "used"
    if "nuevo" in raw or "new" in raw:
        return "new"
    return None


def _format_price_from_result(result: dict[str, Any]) -> str:
    price = result.get("price") or result.get("current_price")
    if isinstance(price, dict):
        price = (
            price.get("amount")
            or price.get("value")
            or price.get("fraction")
            or price.get("cents")
        )
    if price is None:
        return ""
    try:
        amount = int(float(price))
        return f"$ {amount:,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(price)


def normalize_result_from_search_api(result: dict[str, Any]) -> dict[str, Any]:
    winner = result.get("buy_box_winner") if isinstance(result.get("buy_box_winner"), dict) else {}
    offer = {**result, **winner}
    link = str(offer.get("permalink") or offer.get("url") or offer.get("link") or "")
    image = str(offer.get("thumbnail") or offer.get("image") or "")
    pictures = offer.get("pictures") or result.get("pictures") or []
    if not image and pictures and isinstance(pictures[0], dict):
        image = str(pictures[0].get("url") or "")
    images = result.get("images") or []
    if not image and images and isinstance(images[0], dict):
        image = str(images[0].get("url") or images[0].get("secure_url") or "")
    discount = offer.get("discount_percent") or offer.get("discount_rate")
    if discount is None:
        price = offer.get("price")
        original = offer.get("original_price")
        if isinstance(price, dict):
            price = price.get("amount") or price.get("value")
        if isinstance(original, dict):
            original = original.get("amount") or original.get("value")
        try:
            if original and price and float(original) > float(price):
                discount = round(((float(original) - float(price)) / float(original)) * 100)
        except (TypeError, ValueError):
            discount = None
    return {
        "position": 0,
        "title": str(offer.get("title") or offer.get("name") or result.get("title") or result.get("name") or ""),
        "price": _format_price_from_result(offer),
        "link": link,
        "image": image,
        "discount_percent": int(discount) if isinstance(discount, (int, float)) else None,
        "condition": _condition_from_result(offer) or _condition_from_result(result),
    }


def _paging_int(search_api: dict[str, Any], key: str) -> int:
    try:
        return int((search_api.get("paging") or {}).get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _collect_results_from_listing_url(
    first_url: str,
    country: str,
    limit: int,
    fetch_all: bool,
    max_pages: int,
    timeout: int,
    first_api: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    first_api = first_api or search_metadata_from_url(first_url, country, timeout=timeout)
    paging = first_api.get("paging") or {}
    page_limit = int(paging.get("limit") or DEFAULT_PAGE_SIZE)
    total = int(paging.get("total") or 0)
    primary_results = int(paging.get("primary_results") or total or 0)
    accessible_total = min(total, primary_results) if primary_results > 0 and total > 0 else (primary_results or total)
    if not fetch_all:
        target_items = max(1, limit)
    else:
        target_items = accessible_total or limit
    target_pages = max(1, math.ceil(target_items / max(1, page_limit)))
    if max_pages > 0:
        target_pages = min(target_pages, max_pages)

    starts = [1 + (page_limit * idx) for idx in range(target_pages)]
    urls = [first_url] + [insert_start_in_url(first_url, start) for start in starts[1:]]
    pages: dict[int, dict[str, Any]] = {0: first_api}

    def fetch_idx(idx_url: tuple[int, str]) -> tuple[int, dict[str, Any]]:
        idx, url = idx_url
        return idx, search_metadata_from_url(url, country, timeout=timeout)

    if len(urls) > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(urls) - 1)) as executor:
            futures = [executor.submit(fetch_idx, item) for item in enumerate(urls[1:], start=1)]
            for future in concurrent.futures.as_completed(futures):
                try:
                    idx, api = future.result()
                except HTTPError as exc:
                    if exc.code == 404:
                        continue
                    raise
                pages[idx] = api

    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    fetched_raw = 0
    for idx in sorted(pages):
        results = pages[idx].get("results") or []
        fetched_raw += len(results)
        for raw in results:
            item = normalize_result_from_search_api(raw)
            link_key = item.get("link") or item.get("title")
            if not link_key or link_key in seen:
                continue
            seen.add(str(link_key))
            item["position"] = len(items) + 1
            items.append(item)
            if len(items) >= limit:
                break
        if len(items) >= limit:
            break

    meta = {
        "total": total,
        "primary_results": primary_results,
        "accessible_total": accessible_total,
        "page_limit": page_limit,
        "pages_fetched": len(pages),
        "fetched_raw": fetched_raw,
        "search_url": first_url,
        "available_filters": first_api.get("available_filters") or [],
        "filters": first_api.get("filters") or [],
    }
    return items, meta


def _collect_results_split_by_price(
    first_url: str,
    country: str,
    limit: int,
    max_pages: int,
    min_price: int,
    max_price: int,
    timeout: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    lower = max(0, min_price)
    upper = max_price if max_price > 0 else 999_999_999
    seed_ranges: list[tuple[int, int]] = []
    for start in range(0, 100_000, 10_000):
        seed_ranges.append((start, start + 9_999))
    seed_ranges.extend([
        (100_000, 149_999),
        (150_000, 199_999),
        (200_000, 249_999),
        (250_000, 299_999),
        (300_000, 399_999),
        (400_000, 599_999),
        (600_000, 999_999),
        (1_000_000, 1_999_999),
        (2_000_000, 999_999_999),
    ])

    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    pages_fetched = 0
    fetched_raw = 0
    split_ranges: list[dict[str, int]] = []
    total_reported = 0
    page_budget = max_pages if max_pages > 0 else 0

    for seed_low, seed_high in seed_ranges:
        low = max(lower, seed_low)
        high = min(upper, seed_high)
        if low > high:
            continue
        if len(items) >= limit or (page_budget and page_budget <= 0):
            break
        remaining = limit - len(items)
        bucket_pages = page_budget if page_budget else 0
        try:
            bucket_items, bucket_meta = _collect_results_from_listing_url(
                set_price_range_in_url(first_url, low, high), country, remaining, True, bucket_pages, timeout
            )
        except HTTPError as exc:
            if exc.code == 404:
                continue
            raise
        range_total = int(bucket_meta.get("total") or 0)
        if range_total <= 0 and not bucket_items:
            continue
        total_reported += range_total
        pages_fetched += int(bucket_meta.get("pages_fetched") or 0)
        fetched_raw += int(bucket_meta.get("fetched_raw") or 0)
        if page_budget:
            page_budget -= int(bucket_meta.get("pages_fetched") or 0)
        split_ranges.append({"min": low, "max": high, "total": range_total})
        for item in bucket_items:
            link_key = str(item.get("link") or item.get("title") or "")
            if not link_key or link_key in seen:
                continue
            seen.add(link_key)
            item["position"] = len(items) + 1
            items.append(item)
            if len(items) >= limit:
                break

    return items, {
        "total": total_reported,
        "primary_results": 0,
        "accessible_total": total_reported,
        "page_limit": DEFAULT_PAGE_SIZE,
        "pages_fetched": pages_fetched,
        "fetched_raw": fetched_raw,
        "search_url": first_url,
        "available_filters": [],
        "filters": [],
        "split_by_price": True,
        "split_ranges": split_ranges,
    }


def collect_results_from_search_api(
    query: str,
    country: str,
    limit: int,
    fetch_all: bool,
    max_pages: int,
    exclude_international: bool,
    min_price: int,
    max_price: int,
    min_discount: int,
    sort_price: bool,
    condition_filter: str,
    search_url: str | None = None,
    category_url: str | None = None,
    timeout: int = 20,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    first_url = build_initial_listing_url(
        query, country, exclude_international, min_price, max_price, min_discount,
        sort_price, condition_filter, search_url=search_url, category_url=category_url,
    )
    first_api = search_metadata_from_url(first_url, country, timeout=timeout)
    total = _paging_int(first_api, "total")
    primary_results = _paging_int(first_api, "primary_results") or total
    accessible_total = min(total, primary_results) if primary_results > 0 and total > 0 else (primary_results or total)
    if fetch_all and total > accessible_total and limit > accessible_total:
        items, meta = _collect_results_split_by_price(
            first_url, country, limit, max_pages, min_price, max_price, timeout
        )
        meta["split_covered_total"] = meta.get("total", 0)
        meta["total"] = total
        meta["primary_results"] = primary_results
        return items, meta
    return _collect_results_from_listing_url(
        first_url, country, limit, fetch_all, max_pages, timeout, first_api=first_api
    )


def categories_from_search_api(search_api: dict[str, Any]) -> list[dict[str, Any]]:
    for filter_item in search_api.get("available_filters") or []:
        if filter_item.get("id") != "category":
            continue
        out = []
        for value in filter_item.get("values") or []:
            out.append({
                "id": str(value.get("id") or ""),
                "name": str(value.get("name") or ""),
                "count": int(value.get("results") or 0),
                "url": unescape(str(value.get("url") or "")),
            })
        out.sort(key=lambda item: (-item["count"], item["name"]))
        return out
    return []


def fetch_page_with_challenge(
    opener: Any, jar: http.cookiejar.CookieJar, url: str, country: str, timeout: int = 20
) -> str:
    html = _read_html(opener, url, timeout)
    if looks_like_traffic_block(html):
        _raise_traffic_block()
    if "This page requires JavaScript to work" not in html:
        return html

    domain = DOMAIN_BY_COUNTRY[country]
    if not _solve_bm_challenge(jar, domain):
        raise RuntimeError("Bloqueado por anti-bot y no se pudo resolver el desafío.")

    html = _read_html(opener, url, timeout)
    if looks_like_traffic_block(html):
        _raise_traffic_block()
    if "This page requires JavaScript to work" in html:
        raise RuntimeError("Bloqueado por anti-bot después de reintentar.")

    return html


def extract_next_page_url(html: str, current_url: str) -> str | None:
    next_match = re.search(r'<a[^>]+rel="next"[^>]+href="([^"]+)"', html)
    if not next_match:
        next_match = re.search(r'<a[^>]+title="Siguiente"[^>]+href="([^"]+)"', html)
    if not next_match:
        return None
    return urljoin(current_url, unescape(next_match.group(1)))


def collect_results(
    query: str,
    country: str,
    limit: int,
    fetch_all: bool,
    max_pages: int,
    exclude_international: bool,
    min_price: int,
    max_price: int,
    min_discount: int,
    sort_price: bool,
    condition_filter: str,
    search_url: str | None,
    timeout: int = 20,
    quiet: bool = False,
) -> list[dict[str, Any]]:
    opener, jar = _build_opener()
    current_start = 1

    seen_links: set[str] = set()
    collected: list[dict[str, Any]] = []
    page_count = 0
    page_size = DEFAULT_PAGE_SIZE
    empty_streak = 0

    unlimited_pages = max_pages <= 0
    shell_page_streak = 0
    next_url: str | None = search_url.strip() if search_url else None
    while unlimited_pages or page_count < max_pages:
        page_count += 1
        if not quiet:
            _progress(
                "Recolectando paginas",
                page_count,
                (None if unlimited_pages else (max_pages if fetch_all else None)),
            )
        if next_url:
            current_url = next_url
        else:
            current_url = build_search_url_with_start(
                query,
                country,
                current_start,
                exclude_international=exclude_international,
                min_price=min_price,
                max_price=max_price,
                min_discount=min_discount,
                sort_price=sort_price,
                condition_filter=condition_filter,
            )
        html = ""
        last_error: BaseException | None = None
        for attempt in range(REQUEST_RETRIES):
            try:
                html = fetch_page_with_challenge(opener, jar, current_url, country, timeout=timeout)
                last_error = None
                break
            except HTTPError as exc:
                last_error = exc
                if exc.code == 404:
                    break
                if not _is_transient_network_error(exc) or attempt == REQUEST_RETRIES - 1:
                    break
                _sleep_before_retry(attempt)
                opener, jar = _build_opener()
            except (TimeoutError, socket.timeout, ConnectionError, URLError) as exc:
                last_error = exc
                if attempt == REQUEST_RETRIES - 1:
                    break
                _sleep_before_retry(attempt)
                opener, jar = _build_opener()
        if last_error is not None:
            if isinstance(last_error, HTTPError) and last_error.code == 404:
                break
            raise RuntimeError(f"No se pudo leer Mercado Libre tras {REQUEST_RETRIES} intentos: {last_error}") from last_error

        # Some queries return a generic shell page without SSR results.
        # Try an alternate listing URL before giving up on this page.
        if not looks_like_results_page(html):
            fallback_url = build_search_url_with_category(
                query,
                country,
                current_start,
                exclude_international=exclude_international,
                min_price=min_price,
                max_price=max_price,
                min_discount=min_discount,
                sort_price=sort_price,
                condition_filter=condition_filter,
            )
            if not next_url and fallback_url != current_url:
                try:
                    html_alt = fetch_page_with_challenge(opener, jar, fallback_url, country, timeout=timeout)
                    if looks_like_results_page(html_alt):
                        html = html_alt
                except HTTPError:
                    pass

        if not looks_like_results_page(html):
            shell_page_streak += 1
            if shell_page_streak >= 3:
                raise RuntimeError(
                    "Mercado Libre devolvió páginas sin resultados (bloqueo/anti-bot temporal). "
                    "Reintenta en unos minutos."
                )
            if next_url:
                break
            current_start += page_size
            continue
        shell_page_streak = 0

        page_items = parse_results_from_html(html, limit=200)
        if not page_items:
            empty_streak += 1
            if empty_streak >= MAX_EMPTY_PAGES:
                break
            if next_url:
                next_url = extract_next_page_url(html, current_url)
                if not next_url:
                    break
            else:
                current_start += page_size
            continue
        empty_streak = 0

        new_items = 0
        for item in page_items:
            if item["link"] in seen_links:
                continue
            seen_links.add(item["link"])
            item["position"] = len(collected) + 1
            collected.append(item)
            new_items += 1
            if not fetch_all and len(collected) >= limit:
                return collected

        if not fetch_all and len(collected) >= limit:
            return collected

        # If an entire page repeats known links, we're probably at the end.
        if new_items == 0:
            empty_streak += 1
            if empty_streak >= MAX_EMPTY_PAGES:
                break
            if next_url:
                next_url = extract_next_page_url(html, current_url)
                if not next_url:
                    break
            else:
                current_start += page_size
            continue
        empty_streak = 0

        if next_url:
            next_url = extract_next_page_url(html, current_url)
            if not next_url:
                break
        else:
            current_start += page_size

    if not quiet:
        _progress_done()
    return collected if fetch_all else collected[:limit]


def parse_results_from_html(html: str, limit: int = 10) -> list[dict[str, Any]]:
    pattern = re.compile(
        r'<a href="(?P<link>https://[^\"]+)"[^>]*class="poly-component__title"[^>]*>'
        r'(?P<title>.*?)</a>',
        flags=re.DOTALL,
    )

    results: list[dict[str, Any]] = []
    for match in pattern.finditer(html):
        start = match.start()
        end = html.find('<h3 class="poly-component__title-wrapper">', start + 1)
        if end == -1:
            end = min(len(html), start + 6000)

        block = html[start:end]
        raw_link = unescape(match.group("link"))
        link = raw_link.split("#", 1)[0]
        if "mclicks" in link or "mclics" in link:
            continue

        title = clean_html_text(match.group("title"))
        price = extract_price_from_block(block)
        image = extract_image_from_block(block)
        discount_percent = extract_discount_percent_from_block(block)
        condition = extract_condition_from_block(block)

        if not title:
            continue

        results.append(
            {
                "position": len(results) + 1,
                "title": title,
                "price": price,
                "link": link,
                "image": image,
                "discount_percent": discount_percent,
                "condition": condition,
            }
        )
        if len(results) >= limit:
            break

    return results


def fetch_product_condition(link: str, timeout: int = 20) -> str | None:
    try:
        html = fetch_url_html(link, timeout=timeout)
    except Exception:
        return None

    match = re.search(r'"itemCondition"\s*:\s*"([^"]+)"', html)
    if not match:
        return None

    value = unescape(match.group(1)).lower()
    if "newcondition" in value:
        return "new"
    if "usedcondition" in value:
        return "used"
    if "refurbishedcondition" in value or "reconditionedcondition" in value:
        return "reconditioned"
    return None


def enrich_items_with_condition(items: list[dict[str, Any]], max_workers: int = 12) -> None:
    if not items:
        return

    workers = max(1, min(max_workers, 24))
    pending = [item for item in items if not item.get("condition")]
    if not pending:
        return

    def task(item: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        return item, fetch_product_condition(item["link"])

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(task, item) for item in pending]
        done = 0
        total = len(futures)
        for future in concurrent.futures.as_completed(futures):
            item, condition = future.result()
            if condition:
                item["condition"] = condition
            done += 1
            _progress("Leyendo estado", done, total)
    _progress_done()


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


def apply_filters(
    items: list[dict[str, Any]],
    min_price: int,
    max_price: int,
    word: str,
    include_words: list[str],
    min_discount: int,
    exclude_words: list[str],
    strict: bool = False,
    smart_filter: bool = True,
    query: str = "",
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    
    STRONG_ACCESSORIES = {
        "repuesto", "carcasa", "funda", "bolso", "estuche", "mica", "protector",
        "cargador", "cable", "servicio", "reparacion", "arreglo", "tecnico",
        "manual", "caja", "sticker", "calcomania", "mini", "soporte", "adaptador", 
        "vidrio", "templado", "lamina", "desarme", "bisagra", "flex", "cooler", 
        "ventilador", "pin", "jack", "motherboard", "correa", "mouse", "raton", 
        "audifono", "audifonos", "auricular", "auriculares", "mochila", "maletin", 
        "maleta", "parlante", "parlantes", "microfono", "tablet", "ipad", "consola", 
        "nintendo", "xbox", "playstation", "ps4", "ps5", "escritorio", "torre", 
        "gabinete", "impresora", "router", "candado", "base", "chatarra"
    }
    
    WEAK_ACCESSORIES = {
        "pantalla", "teclado", "bateria", "placa", "memoria", "ram", "ssd", "disco", "hdd", "pantallas", "teclados", "baterias", "placas", "memorias", "discos"
    }

    word_lc = normalize_text(word) if word.strip() else ""
    query_lc = normalize_text(query) if query.strip() else ""
    include_words_lc = [normalize_text(w) for w in include_words if str(w).strip()]
    exclude_words_lc = [normalize_text(w) for w in exclude_words if str(w).strip()]
    
    for item in items:
        title_raw = str(item.get("title", ""))
        title_lc = normalize_text(title_raw)
        price_val = parse_price_value(item.get("price"))
        
        if min_price > 0 and (price_val is None or price_val < min_price):
            continue
        if max_price > 0 and (price_val is None or price_val > max_price):
            continue
            
        # 1. Base query word check
        if word_lc and not text_has_term(title_lc, word_lc, whole_word=strict):
            continue
            
        # 2. Include words check
        if include_words_lc and not all(text_has_term(title_lc, w, whole_word=strict) for w in include_words_lc):
            continue
            
        # 3. Exclude words check (manual)
        if exclude_words_lc and any(text_has_term(title_lc, w, whole_word=False) for w in exclude_words_lc):
            continue
            
        # 4. Smart Filter (Anti-Basura)
        if smart_filter:
            query_words = set(word_lc.split()) | set(" ".join(include_words_lc).split()) | set(query_lc.split())
            title_words_list = title_lc.split()
            title_words = set(title_words_list)
            
            found_strong = title_words & STRONG_ACCESSORIES
            if found_strong and not (found_strong & query_words):
                if "para" in found_strong or "compatible" in found_strong or " para " in title_lc or " compatible con " in title_lc:
                    continue
                    
                is_bundle = any(w in title_words for w in ["+", "mas", "regalo", "incluye", "gratis", "con", "y"]) or "+" in title_lc
                if not is_bundle:
                    continue
                
                first_acc_idx = min([title_words_list.index(w) for w in found_strong if w in title_words_list], default=999)
                first_query_idx = min([title_words_list.index(w) for w in query_words if w in title_words_list], default=999)
                if first_acc_idx < first_query_idx:
                    continue
                    
            if title_words_list:
                first_word = title_words_list[0]
                if first_word in WEAK_ACCESSORIES and first_word not in query_words:
                    continue
                
                found_weak = title_words & WEAK_ACCESSORIES
                if found_weak and not (found_weak & query_words):
                    if " para " in title_lc or " compatible con " in title_lc:
                        continue

        discount = item.get("discount_percent")
        if min_discount > 0 and (discount is None or int(discount) < min_discount):
            continue
            
        out.append(item)
    return out


def sort_items_by_price(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key_fn(item: dict[str, Any]) -> tuple[int, int]:
        price = parse_price_value(item.get("price"))
        if price is None:
            return (1, 10**18)
        return (0, price)

    sorted_items = sorted(items, key=key_fn)
    for idx, item in enumerate(sorted_items, start=1):
        item["position"] = idx
    return sorted_items


def xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def build_xlsx_bytes(items: list[dict[str, Any]]) -> bytes:
    headers = ["Posicion", "Titulo", "Precio", "Descuento", "Estado", "Link"]
    rows: list[list[str | int]] = [headers]
    state_map = {"new": "Nuevo", "used": "Usado", "reconditioned": "Reacondicionado"}
    for idx, item in enumerate(items, start=1):
        rows.append(
            [
                idx,
                str(item.get("title") or ""),
                str(item.get("price") or ""),
                (f"{item.get('discount_percent')}%" if item.get("discount_percent") is not None else ""),
                state_map.get(str(item.get("condition") or "").lower(), "N/D"),
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
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{xml_escape(str(value))}</t></is></c>')
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


def export_xlsx(items: list[dict[str, Any]], query: str, country: str, output_path: str | None) -> Path:
    if output_path and output_path != "__AUTO__":
        out = Path(output_path)
    else:
        safe_query = re.sub(r"[^a-zA-Z0-9_-]+", "_", query)[:40].strip("_") or "busqueda"
        out = Path("exports") / f"mercadolibre_{country}_{safe_query}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.xlsx"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(build_xlsx_bytes(items))
    return out


def run(
    query: str,
    limit: int,
    as_json: bool,
    country: str,
    condition_filter: str,
    fetch_all: bool,
    max_pages: int,
    include_condition: bool,
    exclude_international: bool,
    min_price: int,
    max_price: int,
    word_filter: str,
    include_words: list[str],
    exclude_words: list[str],
    min_discount: int,
    sort_price: bool,
    export_xlsx_path: str | None,
    condition_workers: int,
    skip_condition_in_export: bool,
    search_url: str | None,
) -> int:
    parse_limit = limit if condition_filter == "any" else min(max(limit * 4, limit), 80)
    items = collect_results(
        query=query,
        country=country,
        limit=parse_limit,
        fetch_all=fetch_all,
        max_pages=max_pages,
        exclude_international=exclude_international,
        min_price=min_price,
        max_price=max_price,
        min_discount=min_discount,
        sort_price=sort_price,
        condition_filter=condition_filter,
        search_url=search_url,
    )

    # Apply cheap filters first to avoid fetching product condition for thousands of items.
    items = apply_filters(
        items,
        min_price=min_price,
        max_price=max_price,
        word=word_filter,
        include_words=include_words,
        min_discount=min_discount,
        exclude_words=exclude_words,
        query=query,
    )

    if condition_filter != "any":
        for item in items:
            item["condition"] = condition_filter

    needs_condition = (
        include_condition
        or (export_xlsx_path is not None and not skip_condition_in_export)
    )
    if needs_condition and items:
        enrich_items_with_condition(items, max_workers=condition_workers)

    if condition_filter != "any":
        items = [item for item in items if item.get("condition") == condition_filter]
        if not fetch_all:
            items = items[:limit]

    if sort_price:
        items = sort_items_by_price(items)
    else:
        for idx, item in enumerate(items, start=1):
            item["position"] = idx

    if not items:
        # Empty result set is a valid outcome for strict filters.
        if export_xlsx_path is not None:
            out = export_xlsx(items, query=query, country=country, output_path=export_xlsx_path)
            print(f"Excel generado: {out}")
            return 0
        if as_json:
            print("[]")
            return 0
        print("No se encontraron resultados o cambió el HTML de Mercado Libre.")
        return 0

    if export_xlsx_path is not None:
        out = export_xlsx(items, query=query, country=country, output_path=export_xlsx_path)
        print(f"Excel generado: {out}")
        return 0

    if as_json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return 0

    print(f"Resultados para: {query!r} [{country.upper()}] (mostrando {len(items)})\n")
    for item in items:
        print(f"{item['position']}. {item['title']}")
        print(f"   Precio: {item['price'] or 'N/D'}")
        if item.get("discount_percent") is not None:
            print(f"   Descuento: {item['discount_percent']}%")
        if item.get("condition"):
            print(f"   Condición: {item['condition']}")
        print(f"   Link: {item['link']}")

    return 0


def main() -> int:
    started_at = time.perf_counter()
    exit_code = 0
    parser = argparse.ArgumentParser(
        description="Scraper simple de resultados de búsqueda en Mercado Libre."
    )
    parser.add_argument(
        "query",
        nargs="*",
        default=["notebook", "rtx"],
        help="Término de búsqueda (ej: notebook rtx)",
    )
    parser.add_argument(
        "--country",
        choices=sorted(DOMAIN_BY_COUNTRY.keys()),
        default="cl",
        help="País de Mercado Libre (default: cl)",
    )
    parser.add_argument(
        "--limit", type=int, default=10, help="Cantidad máxima de resultados"
    )
    parser.add_argument(
        "--json", action="store_true", help="Imprime los resultados en JSON"
    )
    parser.add_argument(
        "--condition",
        choices=["any", "new", "used", "reconditioned"],
        default="any",
        help="Filtra por condición del producto",
    )
    parser.add_argument(
        "--estado",
        choices=["cualquiera", "nuevo", "usado", "reacondicionado"],
        default=None,
        help="Alias en español de --condition",
    )
    parser.add_argument(
        "--all-results",
        action="store_true",
        help="Intenta recorrer paginación para traer todos los resultados",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=20,
        help="Máximo de páginas a recorrer cuando se usa --all-results (0 = sin límite)",
    )
    parser.add_argument(
        "--include-condition",
        action="store_true",
        help="Incluye condición de cada producto (new/used/reconditioned)",
    )
    parser.add_argument(
        "--include-international",
        action="store_true",
        help="Incluye publicaciones internacionales (por defecto se excluyen)",
    )
    parser.add_argument(
        "--min-price",
        type=int,
        default=0,
        help="Precio mínimo (entero sin separadores)",
    )
    parser.add_argument(
        "--max-price",
        type=int,
        default=0,
        help="Precio máximo (entero sin separadores)",
    )
    parser.add_argument(
        "--word",
        default="",
        help="Filtra resultados por palabra en el título",
    )
    parser.add_argument(
        "--include-word",
        action="append",
        default=[],
        help="Palabra obligatoria en título. Repetir para varias.",
    )
    parser.add_argument(
        "--exclude-word",
        action="append",
        default=[],
        help="Palabra a descartar en título. Repetir para varias.",
    )
    parser.add_argument(
        "--min-discount",
        type=int,
        default=0,
        help="Porcentaje mínimo de descuento (ej: 10)",
    )
    parser.add_argument(
        "--sort-price",
        action="store_true",
        help="Ordena resultados por precio ascendente",
    )
    parser.add_argument(
        "--export-xlsx",
        nargs="?",
        const="__AUTO__",
        default=None,
        help="Exporta a Excel. Opcional: ruta de salida",
    )
    parser.add_argument(
        "--condition-workers",
        type=int,
        default=16,
        help="Cantidad de workers para obtener estado por producto",
    )
    parser.add_argument(
        "--skip-condition-in-export",
        action="store_true",
        help="Acelera export Excel omitiendo la lectura del estado por producto",
    )
    parser.add_argument(
        "--cookie",
        default=None,
        help="Cookie header inline: 'a=1; b=2'",
    )
    parser.add_argument(
        "--cookie-file",
        default=None,
        help="Archivo .txt con cookie header completo",
    )
    parser.add_argument(
        "--search-url",
        default=None,
        help="URL exacta de listado de Mercado Libre para replicar filtros del navegador",
    )

    args = parser.parse_args()
    query = " ".join(args.query).strip()

    condition = args.condition
    if args.estado:
        estado_map = {
            "cualquiera": "any",
            "nuevo": "new",
            "usado": "used",
            "reacondicionado": "reconditioned",
        }
        condition = estado_map[args.estado]

    if not query and not (args.search_url and str(args.search_url).strip()):
        print("Debes indicar un término de búsqueda.")
        exit_code = 2
        return exit_code

    if args.limit < 1:
        print("--limit debe ser >= 1")
        exit_code = 2
        return exit_code

    try:
        configure_cookie_header(args.cookie, args.cookie_file)
        exit_code = run(
            query,
            args.limit,
            args.json,
            args.country,
            condition,
            args.all_results,
            args.max_pages,
            args.include_condition,
            not args.include_international,
            max(0, args.min_price),
            max(0, args.max_price),
            args.word,
            args.include_word,
            args.exclude_word,
            max(0, min(100, args.min_discount)),
            args.sort_price,
            args.export_xlsx,
            max(1, args.condition_workers),
            args.skip_condition_in_export,
            args.search_url,
        )
        return exit_code
    except Exception as exc:
        print(f"Error al obtener datos de Mercado Libre: {exc}", file=sys.stderr)
        exit_code = 1
        return exit_code
    finally:
        elapsed = time.perf_counter() - started_at
        print(f"Tiempo total: {elapsed:.2f}s")


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
import ssl
import time
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any


BASE_URL = "https://www.tuganga.cl"
FCE_URL = f"{BASE_URL}/fce"
PER_PAGE = 40
PAGE_CACHE_TTL_SECONDS = 300
CATEGORY_CACHE_TTL_SECONDS = 900
MAX_WORKERS = 6

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

MODE_CONFIG = {
    "search": ("prgfacets", "busqueda"),
    "offers": ("prglistaofertassolr", "ofertas"),
    "all_offers": ("prgtodasofertassolr", "todasofertas"),
    "minimums": ("prgminimos", "minimos"),
    "best": ("prgmejoresofertas", "ofertas"),
}

PAGE_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
CATEGORY_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}


@dataclass
class SearchOptions:
    query: str = ""
    mode: str = "search"
    stores: list[str] = field(default_factory=list)
    category: str = ""
    min_discount: int = 0
    min_price: int = 0
    max_price: int = 0
    only_available: bool = False
    sort: str = ""
    limit: int = 40
    max_pages: int = 100
    scan_scope: str = "fast"


@dataclass
class SearchResult:
    items: list[dict[str, Any]]
    total_matches: int
    search_url: str
    mode: str
    pages_fetched: int = 0
    fetched_raw: int = 0


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    no_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return no_accents.lower().strip()


def build_search_url(opts: SearchOptions) -> str:
    if opts.mode == "search" and opts.query.strip():
        return f"{BASE_URL}/busqueda?q={urllib.parse.quote_plus(opts.query.strip())}"
    path = {
        "offers": "ofertas",
        "all_offers": "todasofertas",
        "minimums": "minimos",
        "best": "ofertas",
    }.get(opts.mode, "busqueda")
    return f"{BASE_URL}/{path}"


def _request_fce(params: dict[str, Any], timeout: int = 25) -> dict[str, Any]:
    body = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None}).encode("utf-8")
    req = urllib.request.Request(
        FCE_URL,
        data=body,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "es-CL,es;q=0.9,en-US;q=0.8,en;q=0.7",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": BASE_URL,
            "Referer": BASE_URL + "/",
        },
        method="POST",
    )
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(req, timeout=timeout, context=context) as response:
        raw = response.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def _page_cache_key(opts: SearchOptions, page: int) -> str:
    req_name, link = MODE_CONFIG.get(opts.mode, MODE_CONFIG["search"])
    parts = {
        "req": req_name,
        "link": link,
        "page": page,
        "sort": opts.sort.strip(),
        "query": opts.query.strip(),
        "category": opts.category.strip(),
        "stores": sorted(opts.stores),
    }
    return json.dumps(parts, ensure_ascii=False, sort_keys=True)


def _native_filters(opts: SearchOptions) -> list[dict[str, str]]:
    filters: list[dict[str, str]] = []
    if opts.category.strip():
        filters.append({"tipo": "categoria", "valor": opts.category.strip()})
    if len(opts.stores) == 1 and opts.stores[0].strip():
        filters.append({"tipo": "tienda", "valor": opts.stores[0].strip()})
    return filters


def _cache_get(cache: dict, key: str):
    entry = cache.get(key)
    if not entry:
        return None
    expires_at, value = entry
    if expires_at < time.time():
        cache.pop(key, None)
        return None
    return value


def _cache_set(cache: dict, key: str, value: Any, ttl: int) -> None:
    cache[key] = (time.time() + ttl, value)


def _request_page(opts: SearchOptions, page: int) -> dict[str, Any]:
    cache_key = _page_cache_key(opts, page)
    cached = _cache_get(PAGE_CACHE, cache_key)
    if cached is not None:
        return cached

    req_name, link = MODE_CONFIG.get(opts.mode, MODE_CONFIG["search"])
    native_filters = _native_filters(opts)
    params = {
        "reqName": req_name,
        "numPagina": page,
        "link": link,
        "orden": opts.sort,
        "origen": link,
        "facets": "true",
        "prodxpag": PER_PAGE,
        "consulta": opts.query.strip(),
    }
    if native_filters:
        active_filter = native_filters[-1]
        params.update({
            "reqName": "prgfiltrosolr",
            "tipofiltro": active_filter["tipo"],
            "valorfiltro": active_filter["valor"],
            "filtrosJSON": json.dumps(native_filters[:-1], ensure_ascii=False),
        })
    data = _request_fce(
        params
    )
    _cache_set(PAGE_CACHE, cache_key, data, PAGE_CACHE_TTL_SECONDS)
    return data


def categories_for_mode(mode: str = "all_offers", query: str = "") -> list[dict[str, Any]]:
    mode_id = str(mode or "all_offers").strip()
    cache_key = f"{mode_id}|{query.strip()}"
    cached = _cache_get(CATEGORY_CACHE, cache_key)
    if cached is not None:
        return cached

    data = _request_page(SearchOptions(mode=mode_id, query=query.strip(), limit=PER_PAGE), 1)
    raw_categories = data.get("prodXcategoria") or []
    categories: list[dict[str, Any]] = []
    for item in raw_categories:
        name = str(item.get("categoria") or "").strip()
        if not name:
            continue
        categories.append({
            "value": name,
            "label": name,
            "count": int(item.get("numeroProductos") or 0),
        })
    categories.sort(key=lambda item: (-int(item["count"]), normalize_text(item["label"])))
    _cache_set(CATEGORY_CACHE, cache_key, categories, CATEGORY_CACHE_TTL_SECONDS)
    return categories


def _format_price(value: Any) -> str:
    try:
        amount = int(float(value))
    except (TypeError, ValueError):
        return ""
    return f"$ {amount:,}".replace(",", ".")


def _discount(item: dict[str, Any]) -> int:
    raw = item.get("tasa")
    if raw is not None:
        try:
            return max(0, int(float(raw)))
        except (TypeError, ValueError):
            pass
    price = item.get("precio_principal")
    old = item.get("precio_secundario")
    try:
        price_i = int(float(price))
        old_i = int(float(old))
    except (TypeError, ValueError):
        return 0
    if old_i <= 0 or price_i <= 0 or old_i <= price_i:
        return 0
    return round(((old_i - price_i) / old_i) * 100)


def _normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    price = item.get("precio_principal")
    old_price = item.get("precio_secundario")
    discount = _discount(item)
    return {
        "id": str(item.get("id") or ""),
        "title": str(item.get("descripcion_corta") or ""),
        "store": str(item.get("tienda") or ""),
        "brand": str(item.get("marca") or ""),
        "category": str(item.get("categoria") or ""),
        "price": price,
        "formatted_price": _format_price(price),
        "old_price": old_price,
        "formatted_old_price": _format_price(old_price),
        "discount_percentage": discount,
        "difference": item.get("monto_diferencia"),
        "minimum": item.get("minimo"),
        "available": bool(item.get("disponible", True)),
        "url": str(item.get("url") or ""),
        "image": str(item.get("url_img_grande") or item.get("url_img") or ""),
    }


def _parse_price(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if not digits:
        return None
    return int(digits)


def _matches_filters(item: dict[str, Any], opts: SearchOptions) -> bool:
    title = normalize_text(item.get("title", ""))
    query = normalize_text(opts.query)
    if opts.mode != "search" and query and query not in title:
        return False

    local_stores = opts.stores if len(opts.stores) != 1 else []
    stores = [normalize_text(store) for store in local_stores if str(store).strip()]
    if stores and normalize_text(item.get("store", "")) not in stores:
        return False

    category = "" if _native_filters(opts) and opts.category.strip() else normalize_text(opts.category)
    if category and category not in normalize_text(item.get("category", "")):
        return False

    if opts.only_available and not item.get("available", True):
        return False

    price = _parse_price(item.get("price"))
    if opts.min_price > 0 and (price is None or price < opts.min_price):
        return False
    if opts.max_price > 0 and (price is None or price > opts.max_price):
        return False

    if opts.min_discount > 0 and int(item.get("discount_percentage") or 0) < opts.min_discount:
        return False

    return True


def _has_local_filters(opts: SearchOptions) -> bool:
    return bool(
        opts.stores
        or opts.category.strip()
        or opts.min_discount > 0
        or opts.min_price > 0
        or opts.max_price > 0
        or opts.only_available
        or (opts.mode != "search" and opts.query.strip())
    )


def _target_pages(opts: SearchOptions, limit: int, total_matches: int) -> int:
    pages_for_limit = max(1, (limit + PER_PAGE - 1) // PER_PAGE)
    available_pages = max(1, (max(total_matches, 1) + PER_PAGE - 1) // PER_PAGE)
    requested_pages = max(1, int(opts.max_pages or pages_for_limit))
    if opts.scan_scope == "complete":
        target = available_pages
    elif _has_local_filters(opts):
        target = max(pages_for_limit, requested_pages)
    else:
        target = pages_for_limit
    return min(target, available_pages, requested_pages if opts.scan_scope == "complete" else target)


def _fetch_pages_parallel(opts: SearchOptions, pages: list[int]) -> dict[int, dict[str, Any]]:
    if not pages:
        return {}
    results: dict[int, dict[str, Any]] = {}
    workers = min(MAX_WORKERS, len(pages))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_page = {executor.submit(_request_page, opts, page): page for page in pages}
        for future in as_completed(future_to_page):
            page = future_to_page[future]
            results[page] = future.result()
    return results


def execute_search(opts: SearchOptions) -> SearchResult:
    limit = max(1, int(opts.limit or 40))
    all_items: list[dict[str, Any]] = []
    first_page = _request_page(opts, 1)
    total_matches = int(first_page.get("total") or 0)
    target_pages = _target_pages(opts, limit, total_matches)
    pages_data: dict[int, dict[str, Any]] = {1: first_page}
    if target_pages > 1:
        pages_data.update(_fetch_pages_parallel(opts, list(range(2, target_pages + 1))))

    fetched_raw = 0
    for page in sorted(pages_data):
        products = pages_data[page].get("productos") or []
        fetched_raw += len(products)
        for raw_item in products:
            item = _normalize_item(raw_item)
            if _matches_filters(item, opts):
                all_items.append(item)
                if len(all_items) >= limit:
                    break
        if len(all_items) >= limit:
            break

    return SearchResult(
        items=all_items,
        total_matches=total_matches,
        search_url=build_search_url(opts),
        mode=opts.mode,
        pages_fetched=len(pages_data),
        fetched_raw=fetched_raw,
    )


if __name__ == "__main__":
    result = execute_search(SearchOptions(query="notebook", limit=5))
    print(json.dumps(result.items, ensure_ascii=False, indent=2))

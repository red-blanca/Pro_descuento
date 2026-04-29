import json
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any


BASE_URL = "https://knasta.cl"
RESULTS_URL = f"{BASE_URL}/results"
PAGE_CACHE_TTL_SECONDS = 300
CATEGORY_CACHE_TTL_SECONDS = 900
MAX_WORKERS = 8

PAGE_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
CATEGORY_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
RETAIL_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}


@dataclass
class SearchOptions:
    query: str = ""
    retails: list[str] = field(default_factory=list)
    knastaday: int = 0
    category: str = ""
    limit: int = 40
    max_pages: int = 100
    scan_scope: str = "fast"


@dataclass
class SearchResult:
    items: list[dict]
    total_matches: int
    search_url: str
    pages_fetched: int = 0
    fetched_raw: int = 0
    total_pages: int = 0


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


def build_search_url(opts: SearchOptions, page: int = 1) -> str:
    params = []
    if opts.query:
        params.append(("q", opts.query))
    if opts.retails:
        params.append(("partners", ",".join(opts.retails)))
    if opts.knastaday > 0:
        params.append(("knastaday", str(opts.knastaday)))
    if opts.category:
        params.append(("category", opts.category))
    if page > 1:
        params.append(("page", str(page)))

    if params:
        return f"{RESULTS_URL}?{urllib.parse.urlencode(params)}"
    return RESULTS_URL


def _page_cache_key(url: str) -> str:
    return url


def fetch_page(url: str) -> dict[str, Any]:
    cache_key = _page_cache_key(url)
    cached = _cache_get(PAGE_CACHE, cache_key)
    if cached is not None:
        return cached

    req = urllib.request.Request(url, headers={
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "es-CL,es;q=0.9,en-US;q=0.8,en;q=0.7",
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
    data: dict[str, Any] = {}
    if match:
        data = json.loads(match.group(1))
    _cache_set(PAGE_CACHE, cache_key, data, PAGE_CACHE_TTL_SECONDS)
    return data


def _initial_data(data: dict[str, Any]) -> dict[str, Any]:
    return data.get("props", {}).get("pageProps", {}).get("initialData", {}) or {}


def _flatten_categories(node: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    def walk(current: dict[str, Any]) -> None:
        category_id = str(current.get("category_id") or "")
        if category_id and category_id != "0":
            out.append({
                "id": category_id,
                "name": str(current.get("category_name") or ""),
                "path": str(current.get("long_path") or current.get("category_name") or ""),
                "parent_id": str(current.get("parent_id") or ""),
            })
        for child in current.get("children") or []:
            walk(child)

    walk(node)
    return out


def _category_count(category_id: str, base_opts: SearchOptions) -> int:
    opts = SearchOptions(
        query=base_opts.query,
        retails=base_opts.retails,
        knastaday=base_opts.knastaday,
        category=category_id,
        limit=1,
    )
    data = fetch_page(build_search_url(opts, 1))
    return int(_initial_data(data).get("count") or 0)


def categories_for_options(opts: SearchOptions, include_counts: bool = True) -> list[dict[str, Any]]:
    cache_key = json.dumps({
        "query": opts.query,
        "retails": sorted(opts.retails),
        "knastaday": opts.knastaday,
        "include_counts": include_counts,
    }, ensure_ascii=False, sort_keys=True)
    cached = _cache_get(CATEGORY_CACHE, cache_key)
    if cached is not None:
        return cached

    base_data = fetch_page(build_search_url(SearchOptions(
        query=opts.query,
        retails=opts.retails,
        knastaday=opts.knastaday,
        limit=1,
    ), 1))
    categories = _flatten_categories(_initial_data(base_data).get("categories_tree") or {})

    if include_counts and categories:
        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(categories))) as executor:
            future_to_category = {
                executor.submit(_category_count, category["id"], opts): category
                for category in categories
            }
            for future in as_completed(future_to_category):
                category = future_to_category[future]
                try:
                    category["count"] = future.result()
                except Exception:
                    category["count"] = 0
        categories.sort(key=lambda item: (-int(item.get("count") or 0), item["path"]))

    _cache_set(CATEGORY_CACHE, cache_key, categories, CATEGORY_CACHE_TTL_SECONDS)
    return categories


def retails_for_options(opts: SearchOptions) -> list[dict[str, Any]]:
    cache_key = json.dumps({
        "query": opts.query,
        "category": opts.category,
        "knastaday": opts.knastaday,
    }, ensure_ascii=False, sort_keys=True)
    cached = _cache_get(RETAIL_CACHE, cache_key)
    if cached is not None:
        return cached
    data = fetch_page(build_search_url(opts, 1))
    retails = _initial_data(data).get("retails") or []
    out = [
        {
            "id": str(item.get("id") or item.get("alias") or ""),
            "label": str(item.get("label") or item.get("id") or ""),
            "count": int(item.get("count") or 0),
        }
        for item in retails
        if str(item.get("id") or item.get("alias") or "").strip()
    ]
    out.sort(key=lambda item: (-item["count"], item["label"]))
    _cache_set(RETAIL_CACHE, cache_key, out, CATEGORY_CACHE_TTL_SECONDS)
    return out


def _normalize_item(p: dict[str, Any]) -> dict[str, Any]:
    raw_url = str(p.get("url") or "")
    if raw_url.startswith("https//"):
        raw_url = raw_url.replace("https//", "https://")
    elif raw_url.startswith("http//"):
        raw_url = raw_url.replace("http//", "http://")

    if raw_url.startswith("http"):
        final_url = raw_url
    elif raw_url:
        final_url = f"{BASE_URL}{raw_url}"
    else:
        final_url = ""

    return {
        "id": str(p.get("kid") or p.get("product_id") or ""),
        "title": p.get("title", ""),
        "brand": p.get("brand", ""),
        "category": str(p.get("category") or ""),
        "price": p.get("current_price", 0),
        "formatted_price": p.get("formated_current_price", ""),
        "retail": p.get("retail_label", p.get("retail", "")),
        "url": final_url,
        "image": p.get("image", ""),
        "discount_percentage": p.get("percent", 0),
        "last_variation_day": p.get("last_variation_day", ""),
        "is_best_price": bool(p.get("is_best_price", False)),
    }


def _target_pages(opts: SearchOptions, limit: int, total_pages: int) -> int:
    page_limit = max(1, min(500, int(opts.max_pages or 100)))
    if opts.scan_scope == "complete":
        return min(max(1, total_pages), page_limit)
    page_size = 32
    pages_for_limit = max(1, (limit + page_size - 1) // page_size)
    return min(max(1, total_pages), page_limit, pages_for_limit)


def _fetch_pages_parallel(opts: SearchOptions, pages: list[int]) -> dict[int, dict[str, Any]]:
    if not pages:
        return {}
    results: dict[int, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(pages))) as executor:
        future_to_page = {executor.submit(fetch_page, build_search_url(opts, page)): page for page in pages}
        for future in as_completed(future_to_page):
            page = future_to_page[future]
            results[page] = future.result()
    return results


def execute_search(opts: SearchOptions) -> SearchResult:
    limit = max(1, int(opts.limit or 40))
    search_url = build_search_url(opts, 1)
    first_page = fetch_page(search_url)
    first_initial = _initial_data(first_page)
    total_matches = int(first_initial.get("count") or 0)
    total_pages = int(first_initial.get("total_pages") or 1)
    target_pages = _target_pages(opts, limit, total_pages)

    pages_data: dict[int, dict[str, Any]] = {1: first_page}
    if target_pages > 1:
        pages_data.update(_fetch_pages_parallel(opts, list(range(2, target_pages + 1))))

    all_items: list[dict] = []
    fetched_raw = 0
    for page in sorted(pages_data):
        products = _initial_data(pages_data[page]).get("products") or []
        fetched_raw += len(products)
        for product in products:
            all_items.append(_normalize_item(product))
            if len(all_items) >= limit:
                break
        if len(all_items) >= limit:
            break

    return SearchResult(
        items=all_items,
        total_matches=total_matches,
        search_url=search_url,
        pages_fetched=len(pages_data),
        fetched_raw=fetched_raw,
        total_pages=total_pages,
    )


if __name__ == "__main__":
    res = execute_search(SearchOptions(category="20106", knastaday=7, limit=80))
    print(json.dumps(res.items[:5], ensure_ascii=False, indent=2))

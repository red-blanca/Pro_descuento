from __future__ import annotations

import json
import math
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any


API_URL = "https://api.pcfactory.cl/pcfactory-services-catalogo/v1/catalogo/productos"
CATEGORIES_URL = "https://api.pcfactory.cl/api-dex-catalog/v1/catalog/category/PCF/menu"
REQUEST_TIMEOUT = 10
PRODUCTS_PER_PAGE = 48
MAX_WORKERS = 12
_CATEGORIES_CACHE: list[dict[str, Any]] | None = None

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Origin": "https://www.pcfactory.cl",
    "Referer": "https://www.pcfactory.cl/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}


def _fetch_json(url: str) -> Any:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        payload = response.read().decode(charset, errors="replace")
    return json.loads(payload)


def _fetch_page(query: str, page: int, page_size: int = PRODUCTS_PER_PAGE) -> dict[str, Any]:
    params = {
        # The current pcFactory catalog API uses "search" and "size".
        # "keyword" and "prodsPagina" are kept for compatibility with older
        # internal contracts, but are ignored by the current backend.
        "search": query,
        "keyword": query,
        "page": page,
        "size": page_size,
        "prodsPagina": page_size,
    }
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    data = _fetch_json(url)
    if not isinstance(data, dict):
        raise ValueError("pcFactory API returned a non-object JSON payload")
    data["_request_url"] = url
    return data


def fetch_categories() -> list[dict[str, Any]]:
    global _CATEGORIES_CACHE
    if _CATEGORIES_CACHE is not None:
        return _CATEGORIES_CACHE
    data = _fetch_json(CATEGORIES_URL)
    if not isinstance(data, list):
        _CATEGORIES_CACHE = []
        return _CATEGORIES_CACHE
    flattened: list[dict[str, Any]] = []

    def walk(nodes: list[dict[str, Any]], depth: int = 0, parents: list[str] | None = None, parent_id: int | None = None) -> None:
        parents = parents or []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            name = str(node.get("nombre") or "").strip()
            category_id = _as_int(node.get("id"))
            link = str(node.get("link") or "").strip()
            children = node.get("childCategories") if isinstance(node.get("childCategories"), list) else []
            flattened.append({
                "id": category_id,
                "value": str(category_id),
                "label": " / ".join([*parents, name]) if parents else name,
                "name": name,
                "slug": str(node.get("slug") or "").strip(),
                "link": link,
                "depth": depth,
                "parent_id": parent_id,
                "parent_path": parents,
                "has_children": bool(children),
                "child_ids": [_as_int(child.get("id")) for child in children if isinstance(child, dict)],
            })
            walk(children, depth + 1, [*parents, name], category_id)

    walk(data)
    _CATEGORIES_CACHE = flattened
    return _CATEGORIES_CACHE


def _category_by_id(category_id: str | int | None) -> dict[str, Any] | None:
    wanted = str(category_id or "").strip()
    if not wanted:
        return None
    return next((category for category in fetch_categories() if str(category.get("id")) == wanted), None)


def _descendant_category_ids(category_id: str | int | None) -> set[int]:
    selected = _category_by_id(category_id)
    if not selected:
        return set()
    categories = fetch_categories()
    selected_label = str(selected.get("label") or "")
    selected_depth = _as_int(selected.get("depth"))
    ids = {_as_int(selected.get("id"))}
    for category in categories:
        label = str(category.get("label") or "")
        depth = _as_int(category.get("depth"))
        if depth > selected_depth and label.startswith(f"{selected_label} / "):
            ids.add(_as_int(category.get("id")))
    return {value for value in ids if value > 0}


def _category_seed_terms(category_id: str | int | None) -> list[str]:
    selected = _category_by_id(category_id)
    if not selected:
        return []
    categories = fetch_categories()
    selected_label = str(selected.get("label") or "")
    selected_depth = _as_int(selected.get("depth"))
    descendants = [
        category for category in categories
        if _as_int(category.get("depth")) > selected_depth
        and str(category.get("label") or "").startswith(f"{selected_label} / ")
        and not category.get("has_children")
    ]
    if not descendants:
        return [str(selected.get("name") or selected.get("slug") or "").strip()]
    return [str(category.get("name") or category.get("slug") or "").strip() for category in descendants[:24] if str(category.get("name") or category.get("slug") or "").strip()]


def _product_category_id(product: dict[str, Any]) -> int:
    category = product.get("categoria")
    if isinstance(category, dict):
        return _as_int(category.get("id"))
    return 0


def _content(data: dict[str, Any]) -> dict[str, Any]:
    content = data.get("content")
    return content if isinstance(content, dict) else {}


def _items(data: dict[str, Any]) -> list[dict[str, Any]]:
    items = _content(data).get("items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _pageable(data: dict[str, Any]) -> dict[str, Any]:
    pageable = _content(data).get("pageable")
    return pageable if isinstance(pageable, dict) else {}


def _as_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return int(value)
    try:
        text = re.sub(r"[^\d,.-]", "", str(value)).strip()
        if "," in text:
            text = text.replace(".", "").replace(",", ".")
        elif text.count(".") == 1 and len(text.rsplit(".", 1)[-1]) == 3:
            text = text.replace(".", "")
        return int(float(text))
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        text = re.sub(r"[^\d,.-]", "", str(value)).strip()
        if "," in text:
            text = text.replace(".", "").replace(",", ".")
        elif text.count(".") == 1 and len(text.rsplit(".", 1)[-1]) == 3:
            text = text.replace(".", "")
        return float(text)
    except (TypeError, ValueError):
        return default


def _money(value: Any) -> str:
    amount = _as_int(value)
    if amount <= 0:
        return ""
    return f"${amount:,}".replace(",", ".")


def _absolute_url(path: Any) -> str:
    if not path:
        return ""
    value = str(path).strip()
    if value.startswith("http://") or value.startswith("https://"):
        return value
    if not value.startswith("/"):
        value = f"/{value}"
    return f"https://www.pcfactory.cl{value}"


def _product_url(product: dict[str, Any]) -> str:
    slug = str(product.get("slug") or "").strip()
    if slug:
        return f"https://www.pcfactory.cl/producto/{slug}"
    product_id = product.get("id") or product.get("sku")
    if product_id:
        return f"https://www.pcfactory.cl/producto/{product_id}"
    return "https://www.pcfactory.cl/"


def _best_price(prices: dict[str, Any]) -> float:
    cash = _as_float(prices.get("efectivo"))
    if cash > 0:
        return cash
    positives = [
        _as_float(prices.get(key))
        for key in ("bancoEstado", "normal", "referencia")
    ]
    positives = [price for price in positives if price > 0]
    return min(positives) if positives else 0


def _discount_percent(price: float, prices: dict[str, Any]) -> int:
    references = [
        _as_float(prices.get("referencia")),
        _as_float(prices.get("normal")),
    ]
    reference = max((value for value in references if value > price), default=0)
    if price <= 0 or reference <= 0:
        return 0
    return max(0, round((reference - price) * 100 / reference))


def _category_name(product: dict[str, Any]) -> str:
    category = product.get("categoria")
    if isinstance(category, dict):
        return str(category.get("nombre") or "").strip()
    return str(category or "").strip()


def _normalize_product(product: dict[str, Any], position: int) -> dict[str, Any]:
    prices = product.get("precio") if isinstance(product.get("precio"), dict) else {}
    price = _best_price(prices)
    normal_price = _as_float(prices.get("normal"))
    reference_price = _as_float(prices.get("referencia"))
    bank_price = _as_float(prices.get("bancoEstado"))
    product_id = product.get("id") or product.get("sku") or product.get("codigo")
    title = str(product.get("nombre") or product.get("name") or "").strip()
    url = _product_url(product)

    return {
        "id": f"pcfactory#{product_id}" if product_id else f"pcfactory#{position}",
        "sku": str(product_id or ""),
        "title": title,
        "name": title,
        "price": price,
        "formatted_price": _money(price),
        "offer_price": _money(price),
        "offer_price_raw": price,
        "normal_price": _money(normal_price),
        "normal_price_raw": normal_price,
        "reference_price": _money(reference_price),
        "reference_price_raw": reference_price,
        "bank_price": _money(bank_price),
        "bank_price_raw": bank_price,
        "url": url,
        "link": url,
        "image": _absolute_url(product.get("thumbnail") or product.get("image")),
        "store": "pcFactory",
        "brand": str(product.get("marca") or product.get("brand") or "").strip(),
        "category": _category_name(product),
        "category_id": _product_category_id(product),
        "stock": product.get("stock"),
        "available": bool(product.get("stock")),
        "discount_percent": _discount_percent(price, prices),
        "promocion": bool(prices.get("promocion")),
        "outlet": bool(product.get("outlet")),
        "digital": bool(product.get("digital")),
        "position": position,
        "source": "pcfactory",
    }


def _deduplicate(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for product in products:
        key = str(product.get("id") or product.get("slug") or product.get("nombre") or "")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        unique.append(product)
    return unique


def collect_results(
    query: str,
    limit: int = 40,
    scan_scope: str = "complete",
    max_pages: int = 100,
    **kwargs,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Realiza la busqueda directa en la API interna de pcfactory.cl.
    Siempre realiza la busqueda de todas las paginas disponibles para la consulta,
    descargando las paginas adicionales en paralelo con ThreadPoolExecutor.

    Retorna:
        - Una lista de todos los diccionarios de productos normalizados.
        - Un diccionario de metadatos (total de coincidencias, paginas obtenidas, etc.).
    """
    del limit, scan_scope

    cleaned_query = (query or "").strip()
    started = time.perf_counter()
    category_id = str(kwargs.get("category_id") or "").strip()
    category_ids = _descendant_category_ids(category_id)
    category_info = _category_by_id(category_id)
    seed_terms = [cleaned_query] if cleaned_query else _category_seed_terms(category_id)
    seed_terms = [term for term in seed_terms if term]
    if not seed_terms:
        return [], {
            "total": 0,
            "total_matches": 0,
            "pages_fetched": 0,
            "fetched_raw": 0,
            "search_url": API_URL,
            "query_mode": "complete",
            "error": "empty_query",
            "category_id": category_id,
        }

    page_size = PRODUCTS_PER_PAGE
    errors: list[str] = []
    raw_products: list[dict[str, Any]] = []
    successful_pages: set[str] = set()
    total_pages_max = 0
    pages_requested_total = 0
    api_total = 0
    first_search_url = ""

    for term_index, search_term in enumerate(seed_terms):
        try:
            first_page = _fetch_page(search_term, 0, page_size)
        except Exception as exc:
            errors.append(f"{search_term}: {exc}")
            continue

        if not first_search_url:
            first_search_url = str(first_page.get("_request_url") or "")
        first_items = _items(first_page)
        pageable = _pageable(first_page)
        total = _as_int(pageable.get("totalElements"), len(first_items))
        api_total += total
        api_total_pages = _as_int(pageable.get("totalPages"))
        api_page_size = _as_int(pageable.get("pageSize"), page_size) or page_size
        calculated_pages = math.ceil(total / api_page_size) if total > 0 else 1
        total_pages = max(api_total_pages, calculated_pages, 1)
        total_pages_max = max(total_pages_max, total_pages)
        pages_to_fetch = min(total_pages, max_pages if max_pages and max_pages > 0 else total_pages)
        pages_requested_total += pages_to_fetch

        page_results: dict[int, list[dict[str, Any]]] = {0: first_items}
        successful_pages.add(f"{term_index}:0")
        if pages_to_fetch > 1:
            workers = min(MAX_WORKERS, pages_to_fetch - 1)
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(_fetch_page, search_term, page, page_size): page
                    for page in range(1, pages_to_fetch)
                }
                for future in as_completed(futures):
                    page = futures[future]
                    try:
                        page_results[page] = _items(future.result())
                        successful_pages.add(f"{term_index}:{page}")
                    except Exception as exc:
                        errors.append(f"{search_term} page {page}: {exc}")
                        page_results[page] = []

        for page in sorted(page_results):
            raw_products.extend(page_results[page])

    raw_products = _deduplicate(raw_products)
    if category_ids:
        raw_products = [
            product for product in raw_products
            if _product_category_id(product) in category_ids
        ]
    normalized = [
        _normalize_product(product, index)
        for index, product in enumerate(raw_products, start=1)
    ]

    meta = {
        "total": len(normalized) if category_ids else api_total,
        "total_matches": len(normalized) if category_ids else api_total,
        "api_total_matches": api_total,
        "pages_total": total_pages_max,
        "pages_fetched": len(successful_pages),
        "pages_requested": pages_requested_total,
        "page_size": page_size,
        "fetched_raw": len(raw_products),
        "returned": len(normalized),
        "query_mode": "complete",
        "scan_scope_forced": "complete",
        "search_url": first_search_url or f"{API_URL}?search={urllib.parse.quote(seed_terms[0])}",
        "category_id": category_id,
        "category": category_info.get("label") if category_info else "",
        "category_filter_ids": sorted(category_ids),
        "seed_terms": seed_terms,
        "elapsed_seconds": round(time.perf_counter() - started, 2),
    }
    if pages_requested_total < total_pages_max:
        meta["truncated_by_max_pages"] = True
        meta["max_pages"] = max_pages
    if errors:
        meta["errors"] = errors

    return normalized, meta


def _matches_all_words(text: str, words: list[str] | None) -> bool:
    if not words:
        return True
    return all(word.lower() in text for word in words if word and word.strip())


def _matches_no_words(text: str, words: list[str] | None) -> bool:
    if not words:
        return True
    return not any(word.lower() in text for word in words if word and word.strip())


def _searchable_text(item: dict[str, Any]) -> str:
    fields = [
        item.get("title"),
        item.get("name"),
        item.get("brand"),
        item.get("category"),
        item.get("sku"),
    ]
    return " ".join(str(field) for field in fields if field).lower()


def apply_filters(
    items: list[dict[str, Any]],
    min_price: float = 0,
    max_price: float = 0,
    word: str = "",
    include_words: list[str] | None = None,
    exclude_words: list[str] | None = None,
    **kwargs,
) -> list[dict[str, Any]]:
    """
    Filtra localmente la lista de items obtenidos por precio y palabras clave.
    """
    del kwargs

    filtered: list[dict[str, Any]] = []
    required_word = (word or "").strip().lower()
    for item in items:
        price = _as_float(
            item.get("price")
            or item.get("offer_price_raw")
            or item.get("normal_price_raw")
        )
        if min_price > 0 and price < min_price:
            continue
        if max_price > 0 and price > max_price:
            continue

        text = _searchable_text(item)
        if required_word and required_word not in text:
            continue
        if not _matches_all_words(text, include_words):
            continue
        if not _matches_no_words(text, exclude_words):
            continue

        filtered.append(item)

    for idx, item in enumerate(filtered, start=1):
        item["position"] = idx

    return filtered

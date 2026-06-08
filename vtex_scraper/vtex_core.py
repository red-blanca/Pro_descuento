from __future__ import annotations

"""
Motor generico para supermercados que corren sobre la plataforma VTEX
(Jumbo, Santa Isabel, Unimarc, Alvi, ...).

Expone el mismo contrato que el resto de los scrapers del proyecto:
    - fetch_categories(store)
    - collect_results(store, query, limit, scan_scope, max_pages, **kwargs)
    - apply_filters(items, ...)

Usa solo libreria estandar (urllib), sin dependencias externas, igual que
pcfactory.py. Recorre por categoria usando la API publica de catalogo VTEX:

    Arbol de categorias:
        GET {host}/api/catalog_system/pub/category/tree/{depth}
    Productos por categoria:
        GET {host}/api/catalog_system/pub/products/search/?fq=C:/{id}/&_from=0&_to=49
"""

import gzip
import html
import json
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

REQUEST_TIMEOUT = 12
PAGE_SIZE = 50  # VTEX devuelve maximo 50 productos por request (_from/_to)
MAX_WORKERS = 6

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
}

_CATEGORY_CACHE: dict[str, list[dict[str, Any]]] = {}


# ---------------------------------------------------------------------------
# Helpers HTTP / numericos
# ---------------------------------------------------------------------------
def _fetch_json(url: str, host: str) -> Any:
    headers = dict(DEFAULT_HEADERS)
    headers["Origin"] = host
    headers["Referer"] = f"{host}/"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        raw = response.read()
        if (response.headers.get("Content-Encoding") or "").lower() == "gzip":
            raw = gzip.decompress(raw)
        charset = response.headers.get_content_charset() or "utf-8"
        text = raw.decode(charset, errors="replace")
    return json.loads(text)


def _fetch_text(url: str, host: str) -> str:
    headers = dict(DEFAULT_HEADERS)
    headers["Origin"] = host
    headers["Referer"] = f"{host}/"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        raw = response.read()
        if (response.headers.get("Content-Encoding") or "").lower() == "gzip":
            raw = gzip.decompress(raw)
        charset = response.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")


def _as_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        text = re.sub(r"[^\d,.-]", "", str(value)).strip()
        if not text:
            return default
        if "," in text and "." in text:
            text = text.replace(".", "").replace(",", ".")
        elif "," in text:
            text = text.replace(",", ".")
        return float(text)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    return int(round(_as_float(value, default)))


def _money(value: Any) -> str:
    amount = max(0, int(round(_as_float(value))))
    if amount <= 0:
        return ""
    return f"$ {amount:,}".replace(",", ".")


def _label_from_slug(slug: str) -> str:
    text = urllib.parse.unquote(str(slug or "").strip("/"))
    last = text.split("/")[-1] if text else ""
    return " ".join(part.capitalize() for part in last.replace("-", " ").split())


# ---------------------------------------------------------------------------
# Categorias
# ---------------------------------------------------------------------------
def fetch_categories(store: dict[str, Any]) -> list[dict[str, Any]]:
    """Devuelve el arbol de categorias VTEX aplanado, mismo formato que el
    resto del proyecto: {id, value, label, name, depth, parent_id, has_children}."""
    host = store["host"]
    source = store["source"]
    if source in _CATEGORY_CACHE:
        return _CATEGORY_CACHE[source]

    depth = int(store.get("tree_depth") or 3)
    url = f"{host}/api/catalog_system/pub/category/tree/{depth}"
    try:
        data = _fetch_json(url, host)
    except Exception:
        data = []

    flattened: list[dict[str, Any]] = []

    def walk(nodes: Any, parents: list[str], parent_id: str, level: int) -> None:
        if not isinstance(nodes, list):
            return
        for node in nodes:
            if not isinstance(node, dict):
                continue
            cat_id = str(node.get("id") or "").strip()
            name = str(node.get("name") or "").strip()
            children = node.get("children") if isinstance(node.get("children"), list) else []
            label = " / ".join([*parents, name]) if parents else name
            if cat_id and name:
                flattened.append({
                    "id": cat_id,
                    "value": cat_id,
                    "label": label,
                    "name": name,
                    "url": str(node.get("url") or ""),
                    "depth": level,
                    "parent_id": parent_id or "",
                    "has_children": bool(children) or bool(node.get("hasChildren")),
                })
            walk(children, [*parents, name], cat_id, level + 1)

    walk(data, [], "", 0)
    if not flattened:
        flattened = _fetch_categories_from_html(store)
    _CATEGORY_CACHE[source] = flattened
    return flattened


def _fetch_categories_from_html(store: dict[str, Any]) -> list[dict[str, Any]]:
    host = store["host"]
    try:
        text = _fetch_text(host, host)
    except Exception:
        return []

    ignored = (
        "busca",
        "busqueda",
        "prime",
        "mis-compras",
        "locales",
        "informaciones-legales",
        "manifest.json",
        "oferta",
        "ofertas",
        "cyberday",
    )
    seen: set[str] = set()
    categories: list[dict[str, Any]] = []
    for match in re.finditer(r'href=["\']([^"\']+)["\']', text):
        href = html.unescape(match.group(1)).split("?", 1)[0].strip()
        if href.startswith(host):
            href = href[len(host):]
        if not href.startswith("/") or href in {"/", ""}:
            continue
        slug = href.strip("/")
        if not slug or slug.startswith(ignored) or "." in slug:
            continue
        parts = slug.split("/")
        if len(parts) > 3:
            continue
        if slug in seen:
            continue
        seen.add(slug)
        categories.append(
            {
                "id": slug,
                "value": slug,
                "label": " / ".join(_label_from_slug(part) for part in parts),
                "name": _label_from_slug(parts[-1]),
                "url": f"{host}/{slug}",
                "depth": len(parts) - 1,
                "parent_id": "/".join(parts[:-1]),
                "has_children": False,
            }
        )
    return categories


def _category_by_id(store: dict[str, Any], category_id: str | None) -> dict[str, Any] | None:
    wanted = str(category_id or "").strip()
    if not wanted:
        return None
    return next((c for c in fetch_categories(store) if str(c.get("id")) == wanted), None)


# ---------------------------------------------------------------------------
# Normalizacion de producto -> esquema JSON del proyecto
# ---------------------------------------------------------------------------
def _normalize_product(product: dict[str, Any], store: dict[str, Any], position: int) -> dict[str, Any]:
    host = store["host"]
    source = store["source"]
    store_label = store.get("store_label") or source.title()

    pid = str(product.get("productId") or product.get("productReference") or position).strip()
    title = str(product.get("productName") or "").strip()
    brand = str(product.get("brand") or "").strip()

    link = str(product.get("link") or "").strip()
    if not link:
        link_text = str(product.get("linkText") or "").strip()
        link = f"{host}/{link_text}/p" if link_text else f"{host}/"
    elif not link.startswith("http"):
        link = f"{host}/{link.lstrip('/')}"

    price = 0.0
    list_price = 0.0
    image = ""
    available = False

    items_arr = product.get("items") if isinstance(product.get("items"), list) else []
    if items_arr:
        first_item = items_arr[0] if isinstance(items_arr[0], dict) else {}
        images = first_item.get("images") if isinstance(first_item.get("images"), list) else []
        if images and isinstance(images[0], dict):
            image = str(images[0].get("imageUrl") or "")
        sellers = first_item.get("sellers") if isinstance(first_item.get("sellers"), list) else []
        if sellers and isinstance(sellers[0], dict):
            offer = sellers[0].get("commertialOffer") if isinstance(sellers[0].get("commertialOffer"), dict) else {}
            price = _as_float(offer.get("Price"))
            list_price = _as_float(offer.get("ListPrice"))
            available = _as_float(offer.get("AvailableQuantity")) > 0 or bool(offer.get("IsAvailable"))

    if price <= 0:
        price_range = product.get("priceRange") if isinstance(product.get("priceRange"), dict) else {}
        selling = price_range.get("sellingPrice") if isinstance(price_range.get("sellingPrice"), dict) else {}
        price = _as_float(selling.get("lowPrice"))
        list_dict = price_range.get("listPrice") if isinstance(price_range.get("listPrice"), dict) else {}
        list_price = _as_float(list_dict.get("highPrice")) or list_price

    discount = 0
    if list_price > price > 0:
        discount = max(0, min(100, round((list_price - price) * 100 / list_price)))

    category = ""
    cats = product.get("categories")
    if isinstance(cats, list) and cats:
        category = str(cats[0] or "").strip("/").replace("/", " / ")

    return {
        "id": f"{source}#{pid}",
        "sku": pid,
        "title": title,
        "name": title,
        "price": price,
        "price_clp_final": price,
        "price_final_clp": price,
        "formatted_price": _money(price),
        "offer_price_raw": price,
        "price_original": list_price if list_price > price else price,
        "normal_price_raw": list_price,
        "normal_price": _money(list_price) if list_price > price else "",
        "url": link,
        "link": link,
        "image": image,
        "url_imagen": image,
        "store": store_label,
        "brand": brand or None,
        "category": category,
        "discount_percent": discount,
        "available": available,
        "position": position,
        "source": source,
    }


def _extract_react_query_products(text: str) -> list[dict[str, Any]]:
    match = re.search(
        r'<script[^>]+id=["\']__REACT_QUERY_STATE__["\'][^>]*>(.*?)</script>',
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return []
    try:
        data = json.loads(html.unescape(match.group(1)))
    except json.JSONDecodeError:
        return []

    products: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            maybe_products = value.get("products")
            if isinstance(maybe_products, list):
                products.extend([item for item in maybe_products if isinstance(item, dict)])
            for child in value.values():
                if isinstance(child, (dict, list)):
                    walk(child)
        elif isinstance(value, list):
            for child in value:
                if isinstance(child, (dict, list)):
                    walk(child)

    walk(data)
    return products


def _normalize_embedded_product(product: dict[str, Any], store: dict[str, Any], position: int) -> dict[str, Any]:
    host = store["host"]
    source = store["source"]
    store_label = store.get("store_label") or source.title()
    sku = product.get("items", [{}])[0] if isinstance(product.get("items"), list) and product.get("items") else {}
    price = _as_int(sku.get("price"))
    list_price = _as_int(sku.get("listPrice") or price)
    discount = 0
    if list_price > price > 0:
        discount = round((list_price - price) * 100 / list_price, 1)
    images = sku.get("images") if isinstance(sku.get("images"), list) else []
    category_names = product.get("categoryNames") if isinstance(product.get("categoryNames"), list) else []
    slug = str(product.get("slug") or "").strip()
    return {
        "id": str(product.get("productId") or sku.get("skuId") or position),
        "sku": str(sku.get("skuId") or product.get("reference") or ""),
        "title": str(sku.get("name") or product.get("name") or product.get("productName") or "").strip(),
        "name": str(sku.get("name") or product.get("name") or product.get("productName") or "").strip(),
        "brand": str(product.get("brand") or ""),
        "store": store_label,
        "group": store.get("group") or "VTEX",
        "price": price,
        "formatted_price": _money(price),
        "price_original": list_price,
        "formatted_original_price": _money(list_price),
        "link": f"{host}/{slug}/p" if slug else host,
        "url": f"{host}/{slug}/p" if slug else host,
        "image": str(images[0] if images else ""),
        "category": " / ".join(str(value) for value in category_names),
        "discount_percent": discount,
        "available": bool(sku.get("stock", True)),
        "position": position,
        "source": source,
    }


def _fetch_html_products(store: dict[str, Any], category: dict[str, Any] | None, category_id: str, query: str, limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    host = store["host"]
    if category and category.get("url"):
        url = str(category["url"])
    elif category_id:
        url = f"{host}/{category_id.strip('/')}"
    else:
        url = f"{host}/busqueda?ft={urllib.parse.quote(query)}"
    text = _fetch_text(url, host)
    raw = _extract_react_query_products(text)
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for product in raw:
        normalized = _normalize_embedded_product(product, store, len(items) + 1)
        pid = normalized.get("id")
        if pid in seen:
            continue
        seen.add(str(pid))
        if normalized.get("title") and normalized.get("price", 0) > 0:
            items.append(normalized)
        if len(items) >= limit:
            break
    return items, {"html_url": url, "html_products_raw": len(raw)}


# ---------------------------------------------------------------------------
# Busqueda por categoria
# ---------------------------------------------------------------------------
def collect_results(
    store: dict[str, Any],
    query: str = "",
    limit: int = 80,
    scan_scope: str = "complete",
    max_pages: int = 0,
    **kwargs: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Recorre productos de una categoria VTEX (o por palabra clave) y los
    normaliza al esquema JSON del proyecto. Devuelve (items, meta)."""
    started = time.perf_counter()
    host = store["host"]
    source = store["source"]
    sales_channel = str(store.get("sales_channel") or "").strip()

    category_id = str(kwargs.get("category_id") or "").strip()
    cleaned_query = (query or "").strip()
    category = _category_by_id(store, category_id) if category_id else None

    if not category_id and not cleaned_query:
        return [], {
            "source": source,
            "total": 0,
            "total_matches": 0,
            "fetched_raw": 0,
            "pages_fetched": 0,
            "error": "empty_query",
            "elapsed_seconds": round(time.perf_counter() - started, 2),
        }

    target = max(1, min(int(limit or 80), 10000))
    pages_needed = (target + PAGE_SIZE - 1) // PAGE_SIZE
    if scan_scope != "complete":
        pages_needed = min(pages_needed, 2)
    if max_pages and max_pages > 0:
        pages_needed = min(pages_needed, max_pages)
    pages_needed = max(1, pages_needed)

    base = f"{host}/api/catalog_system/pub/products/search"

    def page_url(page_index: int) -> str:
        frm = page_index * PAGE_SIZE
        to = frm + PAGE_SIZE - 1
        params: list[tuple[str, str]] = []
        if cleaned_query:
            params.append(("ft", cleaned_query))
        if category_id:
            params.append(("fq", f"C:/{category_id}/"))
        params.append(("_from", str(frm)))
        params.append(("_to", str(to)))
        if sales_channel:
            params.append(("sc", sales_channel))
        return f"{base}?{urllib.parse.urlencode(params)}"

    raw_products: list[dict[str, Any]] = []
    errors: list[str] = []
    pages_fetched = 0

    def fetch_page(page_index: int) -> tuple[int, list[dict[str, Any]], str | None]:
        try:
            data = _fetch_json(page_url(page_index), host)
            if isinstance(data, list):
                return page_index, [p for p in data if isinstance(p, dict)], None
            return page_index, [], "respuesta no es una lista de productos"
        except Exception as exc:  # noqa: BLE001
            return page_index, [], str(exc)

    _, first_products, first_error = fetch_page(0)
    if first_error:
        errors.append(f"page 0: {first_error}")
    else:
        pages_fetched += 1
        raw_products.extend(first_products)

    should_continue = (
        not first_error
        and len(first_products) >= PAGE_SIZE
        and len(raw_products) < target
    )
    remaining = list(range(1, pages_needed)) if should_continue else []
    if remaining:
        workers = min(MAX_WORKERS, len(remaining))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(fetch_page, p): p for p in remaining}
            for future in as_completed(futures):
                page_index, products, error = future.result()
                if error:
                    errors.append(f"page {page_index}: {error}")
                    continue
                pages_fetched += 1
                raw_products.extend(products)

    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    for product in raw_products:
        pid = str(product.get("productId") or "")
        if pid and pid in seen:
            continue
        if pid:
            seen.add(pid)
        normalized = _normalize_product(product, store, len(items) + 1)
        if not normalized.get("title") or normalized.get("price", 0) <= 0:
            continue
        items.append(normalized)
        if len(items) >= target:
            break

    html_meta: dict[str, Any] = {}
    if not items:
        try:
            items, html_meta = _fetch_html_products(store, category, category_id, cleaned_query, target)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"html fallback: {exc}")

    meta: dict[str, Any] = {
        "source": source,
        "store": store.get("store_label") or source,
        "total": len(items),
        "total_matches": len(items),
        "fetched_raw": len(raw_products) or html_meta.get("html_products_raw", 0),
        "pages_fetched": pages_fetched,
        "pages_requested": pages_needed,
        "page_size": PAGE_SIZE,
        "category_id": category_id,
        "category": category.get("label") if category else "",
        "effective_query": cleaned_query,
        "search_url": html_meta.get("html_url") or page_url(0),
        "query_mode": "html_embedded" if html_meta else "vtex_catalog",
        "elapsed_seconds": round(time.perf_counter() - started, 2),
    }
    if errors:
        meta["errors"] = errors
        if not items:
            meta["warning"] = f"{store.get('store_label') or source}: no se pudieron obtener productos (revisar endpoint/region)."
    return items, meta


# ---------------------------------------------------------------------------
# Filtros locales (precio + palabras)
# ---------------------------------------------------------------------------
def _searchable_text(item: dict[str, Any]) -> str:
    fields = [item.get("title"), item.get("name"), item.get("brand"), item.get("category")]
    return " ".join(str(value) for value in fields if value).lower()


def apply_filters(
    items: list[dict[str, Any]],
    min_price: float = 0,
    max_price: float = 0,
    word: str = "",
    include_words: list[str] | None = None,
    exclude_words: list[str] | None = None,
    min_discount: int = 0,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """Aplica filtros locales (precio, descuento minimo, palabras incluidas/excluidas)."""
    del kwargs
    filtered: list[dict[str, Any]] = []
    required_word = (word or "").strip().lower()
    include = [str(w).strip().lower() for w in include_words or [] if str(w).strip()]
    exclude = [str(w).strip().lower() for w in exclude_words or [] if str(w).strip()]

    for item in items:
        price = _as_float(item.get("price") or item.get("offer_price_raw"))
        if min_price > 0 and price < min_price:
            continue
        if max_price > 0 and price > max_price:
            continue
        if min_discount > 0 and _as_int(item.get("discount_percent")) < min_discount:
            continue
        text = _searchable_text(item)
        if required_word and required_word not in text:
            continue
        if include and not all(w in text for w in include):
            continue
        if exclude and any(w in text for w in exclude):
            continue
        filtered.append(item)

    for index, item in enumerate(filtered, start=1):
        item["position"] = index
    return filtered

from __future__ import annotations

"""
Scraper de Tottus (grupo Falabella). Extraccion por categoria.

Tottus corre sobre la plataforma Falabella, que expone un endpoint JSON de
listado por categoria. Como ese endpoint puede requerir parametros/zona
especificos, este modulo sigue el mismo enfoque tolerante que Lider:

  - Arbol de categorias CURADO (estatico) para la UI.
  - collect_results contra un endpoint JSON configurable (env TOTTUS_API_TEMPLATE)
    con parser flexible y manejo de errores que NO rompe la busqueda global.

Cuando el endpoint no esta configurado, usa Playwright para leer los resultados
SSR incluidos por Next.js en ``__NEXT_DATA__``.
"""

import json
import os
import re
import time
import urllib.parse
import urllib.request
from typing import Any

REQUEST_TIMEOUT = 12

SOURCE = "tottus"
STORE_LABEL = "Tottus"
HOST = "https://www.tottus.cl"
API_ENV = "TOTTUS_API_TEMPLATE"
# Ejemplo (confirmar): "{host}/tottus-cl/category/{category}?page={page}&limit={limit}"
API_TEMPLATE_DEFAULT = ""

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
}

CATEGORIES: list[dict[str, Any]] = [
    {"id": "CATG27055/Despensa", "name": "Despensa"},
    {"id": "CATG27070/Frutas-y-Verduras", "name": "Frutas y Verduras"},
    {"id": "CATG27069/Carnes", "name": "Carnes"},
    {"id": "CATG27127/Pescados-y-Mariscos", "name": "Pescados y Mariscos"},
    {"id": "CATG27139/Lacteos-y-Quesos", "name": "Lacteos y Quesos"},
    {"id": "CATG27109/Fiambres-y-Huevos", "name": "Fiambres y Huevos"},
    {"id": "CATG27075/Panaderia-y-Pasteleria", "name": "Panaderia y Pasteleria"},
    {"id": "CATG29182/Bebestibles", "name": "Bebestibles"},
    {"id": "CATG27083/Cervezas", "name": "Cervezas"},
    {"id": "CATG27084/Vinos-y-Licores", "name": "Vinos y Licores"},
    {"id": "CATG27073/Congelados", "name": "Congelados"},
    {"id": "CATG27074/Aseo-y-Limpieza", "name": "Aseo y Limpieza"},
    {"id": "CATG29426/Perfumeria", "name": "Perfumeria"},
    {"id": "CATG27078/Mascotas", "name": "Mascotas"},
    {"id": "CATG27079/Hogar-y-Ferreteria", "name": "Hogar y Ferreteria"},
]

_NAME_KEYS = ("displayName", "name", "title", "productName", "description")
_PRICE_KEYS = ("price", "salePrice", "sellingPrice", "finalPrice", "currentPrice", "eventPrice")
_LIST_PRICE_KEYS = ("listPrice", "normalPrice", "regularPrice", "originalPrice", "cmrPrice")
_IMAGE_KEYS = ("image", "imageUrl", "thumbnail", "mediaUrls", "img")
_URL_KEYS = ("url", "productUrl", "link", "detailUrl")
_BRAND_KEYS = ("brand", "brandName", "marca")
_ID_KEYS = ("id", "productId", "sku", "skuId", "itemId")


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


def _parse_clp(value: Any) -> float:
    if isinstance(value, list):
        value = value[0] if value else ""
    digits = re.sub(r"[^\d]", "", str(value or ""))
    return float(digits) if digits else 0.0


def _fetch_json(url: str) -> Any:
    headers = dict(DEFAULT_HEADERS)
    headers["Referer"] = f"{HOST}/"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return json.loads(response.read().decode(charset, errors="replace"))


def fetch_categories() -> list[dict[str, Any]]:
    return [
        {
            "id": cat["id"],
            "value": cat["id"],
            "label": cat["name"],
            "name": cat["name"],
            "depth": 0,
            "parent_id": "",
            "has_children": False,
        }
        for cat in CATEGORIES
    ]


def _category_by_id(category_id: str | None) -> dict[str, Any] | None:
    wanted = str(category_id or "").strip()
    if not wanted:
        return None
    return next((c for c in CATEGORIES if c["id"] == wanted), None)


def _first(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return None


def _extract_price(value: Any) -> float:
    if isinstance(value, list) and value:
        return _as_float(value[0] if not isinstance(value[0], dict) else value[0].get("price"))
    if isinstance(value, dict):
        for key in ("value", "amount", "price", "lowPrice"):
            if key in value:
                return _as_float(value[key])
    return _as_float(value)


def _find_product_list(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [p for p in data if isinstance(p, dict)]
    if not isinstance(data, dict):
        return []
    for key in ("products", "items", "results", "records", "productList", "data"):
        value = data.get(key)
        if isinstance(value, list) and value:
            return [p for p in value if isinstance(p, dict)]
    for value in data.values():
        if isinstance(value, (dict, list)):
            found = _find_product_list(value)
            if found:
                return found
    return []


def _normalize_product(product: dict[str, Any], position: int) -> dict[str, Any]:
    pid = str(_first(product, _ID_KEYS) or position).strip()
    title = str(_first(product, _NAME_KEYS) or "").strip()
    brand = str(_first(product, _BRAND_KEYS) or "").strip()

    image_raw = _first(product, _IMAGE_KEYS)
    if isinstance(image_raw, list) and image_raw:
        image = str(image_raw[0])
    elif isinstance(image_raw, dict):
        image = str(image_raw.get("url") or "")
    else:
        image = str(image_raw or "")

    link = str(_first(product, _URL_KEYS) or "").strip()
    if link and not link.startswith("http"):
        link = f"{HOST}/{link.lstrip('/')}"
    if not link:
        link = f"{HOST}/"

    price = _extract_price(_first(product, _PRICE_KEYS))
    list_price = _extract_price(_first(product, _LIST_PRICE_KEYS))

    discount = 0
    if list_price > price > 0:
        discount = max(0, min(100, round((list_price - price) * 100 / list_price)))

    return {
        "id": f"{SOURCE}#{pid}",
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
        "store": STORE_LABEL,
        "brand": brand or None,
        "category": "",
        "discount_percent": discount,
        "available": True,
        "position": position,
        "source": SOURCE,
    }


def _normalize_next_product(
    product: dict[str, Any],
    position: int,
    category_name: str = "",
) -> dict[str, Any]:
    prices = product.get("prices") if isinstance(product.get("prices"), list) else []
    current_prices = [
        _parse_clp(entry.get("price"))
        for entry in prices
        if isinstance(entry, dict) and not entry.get("crossed")
    ]
    crossed_prices = [
        _parse_clp(entry.get("price"))
        for entry in prices
        if isinstance(entry, dict) and entry.get("crossed")
    ]
    current_prices = [price for price in current_prices if price > 0]
    crossed_prices = [price for price in crossed_prices if price > 0]
    price = min(current_prices, default=0.0)
    list_price = max(crossed_prices, default=price)

    normalized = _normalize_product(
        {
            "productId": product.get("productId") or product.get("skuId"),
            "displayName": product.get("displayName"),
            "brand": product.get("brand"),
            "mediaUrls": product.get("mediaUrls") or product.get("media"),
            "url": product.get("url"),
            "price": price,
            "listPrice": list_price,
        },
        position,
    )
    normalized["category"] = category_name
    normalized["available"] = bool(product.get("availability", True))
    return normalized


def _browser_url(query: str, category_id: str, page_number: int = 1) -> str:
    if query:
        url = f"{HOST}/tottus-cl/search?Ntt={urllib.parse.quote(query)}"
    else:
        url = f"{HOST}/tottus-cl/lista/{category_id.strip('/')}"
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}page={page_number}" if page_number > 1 else url


def _collect_browser_results(
    query: str,
    category_id: str,
    category: dict[str, Any] | None,
    limit: int,
    max_pages: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001
        return [], {"warning": f"Tottus requiere Playwright: {exc}"}

    headless = os.environ.get("TOTTUS_BROWSER_HEADLESS", "0").strip().lower() in {"1", "true", "yes"}
    channel = os.environ.get("TOTTUS_BROWSER_CHANNEL", "chrome").strip() or None
    # El SSR ignora ?page=2 y vuelve a entregar la primera pagina.
    page_limit = 1
    raw_products: list[dict[str, Any]] = []
    search_url = _browser_url(query, category_id)
    search_warning = ""

    try:
        with sync_playwright() as playwright:
            launch_options: dict[str, Any] = {"headless": headless}
            if channel:
                launch_options["channel"] = channel
            try:
                browser = playwright.chromium.launch(**launch_options)
            except Exception:
                browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(locale="es-CL", ignore_https_errors=True)

            targets: list[tuple[str, str, int]] = []
            if category_id:
                targets.append(("", category_id, page_limit))
            elif query:
                targets.append((query, "", page_limit))
                targets.extend(("", cat["id"], 1) for cat in CATEGORIES)

            for target_query, target_category, target_pages in targets:
                for page_number in range(1, target_pages + 1):
                    current_url = _browser_url(target_query, target_category, page_number)
                    page.goto(current_url, wait_until="domcontentloaded", timeout=60_000)
                    if "526" in page.title() or "invalid ssl" in page.title().lower():
                        if target_query:
                            search_warning = (
                                "Tottus: /search respondio 526; se uso busqueda local "
                                "sobre categorias."
                            )
                            break
                        continue
                    next_data = page.locator("#__NEXT_DATA__")
                    try:
                        next_data.wait_for(state="attached", timeout=15_000)
                    except Exception:
                        if target_query:
                            search_warning = (
                                "Tottus: /search fue bloqueado; se uso busqueda local "
                                "sobre categorias."
                            )
                            break
                        continue
                    payload = json.loads(next_data.text_content() or "{}")
                    page_products = payload.get("props", {}).get("pageProps", {}).get("results", [])
                    if not isinstance(page_products, list) or not page_products:
                        break
                    for product in page_products:
                        if not isinstance(product, dict):
                            continue
                        text = " ".join(
                            str(product.get(key) or "")
                            for key in ("displayName", "brand")
                        ).lower()
                        if query and not target_query and query.lower() not in text:
                            continue
                        raw_products.append(product)
                    if len(raw_products) >= limit or len(page_products) < 48:
                        break
                if len(raw_products) >= limit:
                    break
            browser.close()
    except Exception as exc:  # noqa: BLE001
        return [], {
            "search_url": search_url,
            "warning": f"Tottus: fallo Playwright ({exc}).",
        }

    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    category_name = category.get("name") if category else ""
    for product in raw_products:
        normalized = _normalize_next_product(product, len(items) + 1, category_name)
        if normalized["id"] in seen:
            continue
        seen.add(normalized["id"])
        if normalized["title"] and normalized["price"] > 0:
            items.append(normalized)
        if len(items) >= limit:
            break
    meta = {"search_url": search_url, "fetched_raw": len(raw_products)}
    if search_warning:
        meta["warning"] = search_warning
    return items, meta


def collect_results(
    query: str = "",
    limit: int = 80,
    scan_scope: str = "complete",
    max_pages: int = 0,
    **kwargs: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    started = time.perf_counter()
    category_id = str(kwargs.get("category_id") or "").strip()
    cleaned_query = (query or "").strip()
    category = _category_by_id(category_id)
    target = max(1, min(int(limit or 80), 5000))

    base_meta = {
        "source": SOURCE,
        "store": STORE_LABEL,
        "category_id": category_id,
        "category": category.get("name") if category else "",
        "effective_query": cleaned_query,
        "query_mode": "falabella_json",
    }

    if not category_id and not cleaned_query:
        base_meta.update({"total": 0, "total_matches": 0, "error": "empty_query",
                          "elapsed_seconds": round(time.perf_counter() - started, 2)})
        return [], base_meta

    template = os.environ.get(API_ENV) or API_TEMPLATE_DEFAULT
    if not template:
        items, browser_meta = _collect_browser_results(
            cleaned_query,
            category_id,
            category,
            target,
            max_pages,
        )
        base_meta.update(browser_meta)
        base_meta.update({
            "query_mode": "playwright_next_data",
            "total": len(items),
            "total_matches": len(items),
            "elapsed_seconds": round(time.perf_counter() - started, 2),
        })
        return items, base_meta

    url = template.format(
        host=HOST,
        category=urllib.parse.quote(category_id),
        query=urllib.parse.quote(cleaned_query),
        limit=target,
        page=1,
    )

    try:
        data = _fetch_json(url)
    except Exception as exc:  # noqa: BLE001
        base_meta.update({"total": 0, "total_matches": 0, "error": str(exc),
                          "warning": f"Tottus: fallo la peticion ({exc}).",
                          "search_url": url,
                          "elapsed_seconds": round(time.perf_counter() - started, 2)})
        return [], base_meta

    raw_products = _find_product_list(data)
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for product in raw_products:
        normalized = _normalize_product(product, len(items) + 1)
        if normalized["id"] in seen:
            continue
        seen.add(normalized["id"])
        if not normalized.get("title") or normalized.get("price", 0) <= 0:
            continue
        items.append(normalized)
        if len(items) >= target:
            break

    base_meta.update({
        "total": len(items),
        "total_matches": len(items),
        "fetched_raw": len(raw_products),
        "search_url": url,
        "elapsed_seconds": round(time.perf_counter() - started, 2),
    })
    if not items:
        base_meta["warning"] = "Tottus: la respuesta no contenia productos reconocibles. Ajusta el parser/endpoint (Paso 1)."
    return items, base_meta


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

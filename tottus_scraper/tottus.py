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
import unicodedata
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
OFFERS_CATEGORY_ID = "__offers__"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
}

CATEGORIES: list[dict[str, Any]] = [
    {"id": OFFERS_CATEGORY_ID, "name": "Ofertas"},
    {"id": "CATG27055/Despensa", "name": "Despensa"},
    {"id": "CATG27070/Frutas-y-Verduras", "name": "Frutas y Verduras"},
    {"id": "CATG27069/Carnes", "name": "Carnes"},
    {"id": "CATG27127/Pescados-y-Mariscos", "name": "Pescados y Mariscos"},
    {"id": "CATG27139/Lacteos-y-Quesos", "name": "Lacteos y Quesos"},
    {"id": "CATG27109/Fiambres-y-Huevos", "name": "Fiambres y Huevos"},
    {"id": "CATG27075/Panaderia-y-Pasteleria", "name": "Panaderia y Pasteleria"},
    {"id": "CATG29182/Bebestibles", "name": "Bebestibles"},
    {"id": "CATG27609/Energeticas", "name": "Bebidas Energeticas"},
    {"id": "CATG27218/Isotonicas-y-Energeticas", "name": "Isotonicas y Energeticas"},
    {"id": "CATG27083/Cervezas", "name": "Cervezas"},
    {"id": "CATG27084/Vinos-y-Licores", "name": "Vinos y Licores"},
    {"id": "CATG27073/Congelados", "name": "Congelados"},
    {"id": "CATG27074/Aseo-y-Limpieza", "name": "Aseo y Limpieza"},
    {"id": "CATG29426/Perfumeria", "name": "Perfumeria"},
    {"id": "CATG27078/Mascotas", "name": "Mascotas"},
    {"id": "CATG27079/Hogar-y-Ferreteria", "name": "Hogar y Ferreteria"},
]

# Colecciones enlazadas desde /tottus-cl/content/ofertas-tottus.
OFFER_COLLECTIONS = [
    "CATG10215/Tottus-a-Lucas",
    "CATG27092/Pollo",
    "CATG10217/Abarrotes",
    "CATG27134/Papeles-para-el-Hogar",
    "CATG10222/Lacteos",
    "CATG10223/Lavado-y-Aseo",
    "CATG27088/Electro-y-Tecnologia",
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
        url = f"{HOST}/tottus-cl/buscar?Ntt={urllib.parse.quote(query)}"
    else:
        url = f"{HOST}/tottus-cl/lista/{category_id.strip('/')}"
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}page={page_number}" if page_number > 1 else url


def _normalized_text(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()


def _categories_for_query(query: str) -> list[dict[str, Any]]:
    text = _normalized_text(query)
    keyword_categories = {
        "aceite": "CATG27055/Despensa",
        "arroz": "CATG27055/Despensa",
        "fideo": "CATG27055/Despensa",
        "galleta": "CATG27055/Despensa",
        "leche": "CATG27139/Lacteos-y-Quesos",
        "queso": "CATG27139/Lacteos-y-Quesos",
        "yog": "CATG27139/Lacteos-y-Quesos",
        "carne": "CATG27069/Carnes",
        "pollo": "CATG27069/Carnes",
        "pescado": "CATG27127/Pescados-y-Mariscos",
        "cerveza": "CATG27083/Cervezas",
        "vino": "CATG27084/Vinos-y-Licores",
        "bebida": "CATG29182/Bebestibles",
        "jugo": "CATG29182/Bebestibles",
        "energet": "CATG27609/Energeticas",
        "isotonic": "CATG27218/Isotonicas-y-Energeticas",
        "pan": "CATG27075/Panaderia-y-Pasteleria",
        "shampoo": "CATG29426/Perfumeria",
        "jabon": "CATG29426/Perfumeria",
        "detergente": "CATG27074/Aseo-y-Limpieza",
        "limpieza": "CATG27074/Aseo-y-Limpieza",
        "perro": "CATG27078/Mascotas",
        "gato": "CATG27078/Mascotas",
    }
    preferred_ids = [
        category_id
        for keyword, category_id in keyword_categories.items()
        if keyword in text
    ]
    matched = [
        cat for cat in CATEGORIES
        if cat["id"] in preferred_ids or any(word in _normalized_text(cat["name"]) for word in text.split())
    ]
    if matched:
        return matched[:3]
    # Para terminos desconocidos hace un sondeo acotado, no recorre todo el sitio.
    return CATEGORIES[:3]


def _matches_query(product: dict[str, Any], query: str) -> bool:
    text = _normalized_text(" ".join(
        str(product.get(key) or "")
        for key in ("displayName", "brand")
    ))
    words = [word for word in _normalized_text(query).split() if word]
    return bool(words) and all(word in text for word in words)


def _has_discount(product: dict[str, Any]) -> bool:
    return any(
        isinstance(price, dict) and price.get("crossed") and _parse_clp(price.get("price")) > 0
        for price in product.get("prices", [])
    )


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

    channel = os.environ.get("TOTTUS_BROWSER_CHANNEL", "").strip() or None
    # El SSR ignora ?page=2 y vuelve a entregar la primera pagina.
    page_limit = 1
    raw_products: list[dict[str, Any]] = []
    search_url = _browser_url(query, category_id)
    if category_id == OFFERS_CATEGORY_ID:
        search_url = f"{HOST}/tottus-cl/content/ofertas-tottus"
    search_warning = ""
    deadline = time.perf_counter() + (90 if category_id == OFFERS_CATEGORY_ID else 25)
    direct_search_succeeded = False
    offer_stats = {
        "collections_total": len(OFFER_COLLECTIONS),
        "collections_scanned": 0,
        "collections_with_products": 0,
        "collections_blocked": 0,
    }

    try:
        with sync_playwright() as playwright:
            launch_options: dict[str, Any] = {"headless": True}
            if channel:
                launch_options["channel"] = channel
            try:
                browser = playwright.chromium.launch(**launch_options)
            except Exception:
                browser = playwright.chromium.launch(headless=True)
            page_options = {
                "locale": "es-CL",
                "ignore_https_errors": True,
                "user_agent": DEFAULT_HEADERS["User-Agent"],
                "extra_http_headers": {"Accept-Language": DEFAULT_HEADERS["Accept-Language"]},
            }
            page = browser.new_page(
                locale="es-CL",
                ignore_https_errors=True,
                user_agent=DEFAULT_HEADERS["User-Agent"],
                extra_http_headers={"Accept-Language": DEFAULT_HEADERS["Accept-Language"]},
            )
            page.set_default_timeout(5_000)

            targets: list[tuple[str, str, int]] = []
            if category_id == OFFERS_CATEGORY_ID:
                targets.extend(("", offer_category, 1) for offer_category in OFFER_COLLECTIONS)
            elif category_id:
                targets.append(("", category_id, page_limit))
            elif query:
                targets.append((query, "", page_limit))
                targets.extend(("", cat["id"], 1) for cat in _categories_for_query(query))

            for target_query, target_category, target_pages in targets:
                if time.perf_counter() >= deadline:
                    search_warning = "Tottus: busqueda parcial por limite de tiempo."
                    break
                if category_id == OFFERS_CATEGORY_ID:
                    if offer_stats["collections_scanned"] > 0:
                        page.close()
                        page = browser.new_page(**page_options)
                        page.set_default_timeout(5_000)
                    offer_stats["collections_scanned"] += 1
                for page_number in range(1, target_pages + 1):
                    current_url = _browser_url(target_query, target_category, page_number)
                    try:
                        page.goto(current_url, wait_until="domcontentloaded", timeout=10_000)
                    except Exception:
                        search_warning = "Tottus: una pagina no respondio dentro del limite de tiempo."
                        if category_id == OFFERS_CATEGORY_ID:
                            offer_stats["collections_blocked"] += 1
                        break
                    if "526" in page.title() or "invalid ssl" in page.title().lower():
                        if target_query:
                            search_warning = (
                                "Tottus: /buscar respondio 526; se uso busqueda local "
                                "sobre categorias."
                            )
                            break
                        continue
                    next_data = page.locator("#__NEXT_DATA__")
                    try:
                        next_data.wait_for(state="attached", timeout=5_000)
                    except Exception:
                        if target_query:
                            search_warning = (
                                "Tottus: /buscar fue bloqueado; se uso busqueda local "
                                "sobre categorias."
                            )
                            break
                        search_warning = "Tottus: la categoria fue bloqueada por Cloudflare."
                        if category_id == OFFERS_CATEGORY_ID:
                            offer_stats["collections_blocked"] += 1
                        continue
                    payload = json.loads(next_data.text_content() or "{}")
                    page_products = payload.get("props", {}).get("pageProps", {}).get("results", [])
                    if not isinstance(page_products, list) or not page_products:
                        if target_query:
                            direct_search_succeeded = True
                        break
                    if category_id == OFFERS_CATEGORY_ID:
                        offer_stats["collections_with_products"] += 1
                    if target_query:
                        direct_search_succeeded = True
                    for product in page_products:
                        if not isinstance(product, dict):
                            continue
                        if category_id == OFFERS_CATEGORY_ID and not _has_discount(product):
                            continue
                        if query and not _matches_query(product, query):
                            continue
                        raw_products.append(product)
                    if (
                        category_id != OFFERS_CATEGORY_ID
                        and len(raw_products) >= limit
                    ) or len(page_products) < 48:
                        break
                if category_id != OFFERS_CATEGORY_ID and len(raw_products) >= limit:
                    break
                if target_query and direct_search_succeeded:
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
        if category_id != OFFERS_CATEGORY_ID and len(items) >= limit:
            break
    meta = {"search_url": search_url, "fetched_raw": len(raw_products)}
    if category_id == OFFERS_CATEGORY_ID:
        meta.update(offer_stats)
        partial = (
            offer_stats["collections_scanned"] < offer_stats["collections_total"]
            or offer_stats["collections_blocked"] > 0
        )
        meta["partial"] = partial
        if partial:
            if len(raw_products) >= limit and offer_stats["collections_blocked"] == 0:
                search_warning = (
                    "Tottus Ofertas: resultados parciales por limite solicitado; "
                    f"{offer_stats['collections_scanned']}/{offer_stats['collections_total']} "
                    "colecciones revisadas, ninguna bloqueada."
                )
            else:
                search_warning = (
                    "Tottus Ofertas: resultados parciales; "
                    f"{offer_stats['collections_scanned']}/{offer_stats['collections_total']} "
                    f"colecciones revisadas, {offer_stats['collections_blocked']} bloqueadas."
                )
    if not raw_products and not search_warning:
        search_warning = "Tottus: la pagina no contenia productos reconocibles."
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

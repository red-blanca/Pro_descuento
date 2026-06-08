from __future__ import annotations

"""
Scraper de Tottus (grupo Falabella). Extraccion por categoria.

Tottus corre sobre la plataforma Falabella, que expone un endpoint JSON de
listado por categoria. Como ese endpoint puede requerir parametros/zona
especificos, este modulo sigue el mismo enfoque tolerante que Lider:

  - Arbol de categorias CURADO (estatico) para la UI.
  - collect_results contra un endpoint JSON configurable (env TOTTUS_API_TEMPLATE)
    con parser flexible y manejo de errores que NO rompe la busqueda global.

Confirmar el endpoint real en el Paso 1 del plan (o usar fallback Playwright).
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
    {"id": "despensa", "name": "Despensa"},
    {"id": "frutas-y-verduras", "name": "Frutas y Verduras"},
    {"id": "carnes-y-pescados", "name": "Carnes y Pescados"},
    {"id": "lacteos-y-huevos", "name": "Lacteos y Huevos"},
    {"id": "panaderia", "name": "Panaderia"},
    {"id": "bebidas", "name": "Bebidas"},
    {"id": "vinos-cervezas-y-licores", "name": "Vinos, Cervezas y Licores"},
    {"id": "snacks-y-dulces", "name": "Snacks y Dulces"},
    {"id": "congelados", "name": "Congelados"},
    {"id": "limpieza", "name": "Limpieza"},
    {"id": "cuidado-personal", "name": "Cuidado Personal"},
    {"id": "mascotas", "name": "Mascotas"},
    {"id": "bebes", "name": "Bebes"},
    {"id": "hogar", "name": "Hogar"},
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
        base_meta.update({
            "total": 0,
            "total_matches": 0,
            "warning": (
                "Tottus: endpoint de catalogo no configurado. Define la variable "
                f"de entorno {API_ENV} con el template del endpoint JSON "
                "(ver Paso 1 del plan) o usa el fallback Playwright."
            ),
            "elapsed_seconds": round(time.perf_counter() - started, 2),
        })
        return [], base_meta

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

from __future__ import annotations

"""
Motor para supermercados Walmart Chile: Lider y acuenta.

Lider/acuenta NO corren sobre VTEX, por lo que usan su propio motor. El sitio
entrega su catalogo via un endpoint JSON interno. Como ese endpoint puede
cambiar y/o exigir cabeceras de region (Curico), este motor:

  1. Expone un arbol de categorias CURADO (estatico) para que el selector de
     categorias de la UI funcione siempre, aun sin red.
  2. Intenta extraer productos contra un endpoint JSON configurable.
     El template del endpoint se toma de la variable de entorno
     LIDER_API_TEMPLATE / ACUENTA_API_TEMPLATE o del valor por defecto de la
     tienda. Si la peticion falla o no hay endpoint confirmado, devuelve una
     lista vacia con un 'warning' (NO lanza excepcion), para no romper la
     busqueda global.
  3. El parser de productos es flexible: reconoce los nombres de campo mas
     comunes (name/displayName/title, price/prices, image/images, url, brand),
     de modo que al confirmar el endpoint real (Paso 1 del plan) normalmente
     basta con ajustar la URL.

Si el sitio bloquea las peticiones directas, la alternativa es replicar el
patron de fallback con Playwright que ya usa el scraper de AliExpress.
"""

import json
import os
import re
import time
import urllib.parse
import urllib.request
from typing import Any

REQUEST_TIMEOUT = 12
PAGE_SIZE = 40

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
}

# Arbol curado de categorias de supermercado (comun a Lider y acuenta).
# Los 'id' son slugs estables usados para construir la URL de la categoria.
SUPERMARKET_CATEGORIES: list[dict[str, Any]] = [
    {"id": "despensa", "name": "Despensa"},
    {"id": "frutas-y-verduras", "name": "Frutas y Verduras"},
    {"id": "carniceria-y-pescaderia", "name": "Carniceria y Pescaderia"},
    {"id": "lacteos", "name": "Lacteos"},
    {"id": "huevos", "name": "Huevos"},
    {"id": "panaderia-y-pasteleria", "name": "Panaderia y Pasteleria"},
    {"id": "desayuno-y-dulces", "name": "Desayuno y Dulces"},
    {"id": "bebidas-y-licores", "name": "Bebidas y Licores"},
    {"id": "snacks-y-confites", "name": "Snacks y Confites"},
    {"id": "congelados", "name": "Congelados"},
    {"id": "limpieza", "name": "Limpieza"},
    {"id": "cuidado-personal", "name": "Cuidado Personal"},
    {"id": "mascotas", "name": "Mascotas"},
    {"id": "bebes-y-ninos", "name": "Bebes y Ninos"},
    {"id": "hogar-y-aseo", "name": "Hogar y Aseo"},
    {"id": "electro-y-tecnologia", "name": "Electro y Tecnologia"},
]


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


def _parse_clp_text(value: Any) -> int:
    digits = re.sub(r"[^\d]", "", str(value or ""))
    return int(digits) if digits else 0


def _fetch_json(url: str, host: str) -> Any:
    headers = dict(DEFAULT_HEADERS)
    headers["Referer"] = f"{host}/"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return json.loads(response.read().decode(charset, errors="replace"))


def fetch_categories(store: dict[str, Any]) -> list[dict[str, Any]]:
    configured = store.get("categories")
    if isinstance(configured, list) and configured:
        return [
            {
                "id": category_id,
                "value": category_id,
                "label": name,
                "name": name,
                "depth": 0,
                "parent_id": "",
                "has_children": False,
            }
            for category_id, name in configured
        ]
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
        for cat in SUPERMARKET_CATEGORIES
    ]


def _category_by_id(category_id: str | None) -> dict[str, Any] | None:
    wanted = str(category_id or "").strip()
    if not wanted:
        return None
    return next((c for c in SUPERMARKET_CATEGORIES if c["id"] == wanted), None)


def _configured_category_by_id(store: dict[str, Any], category_id: str | None) -> dict[str, Any] | None:
    wanted = str(category_id or "").strip()
    for category in store.get("categories") or []:
        if isinstance(category, (list, tuple)) and len(category) >= 2 and str(category[0]) == wanted:
            return {"id": str(category[0]), "name": str(category[1])}
    return _category_by_id(wanted)


# Campos candidatos para el parser flexible.
_NAME_KEYS = ("displayName", "name", "title", "productName", "description")
_PRICE_KEYS = ("price", "salePrice", "sellingPrice", "finalPrice", "currentPrice", "basePrice")
_LIST_PRICE_KEYS = ("listPrice", "normalPrice", "regularPrice", "wasPrice", "priceBeforeDiscount")
_IMAGE_KEYS = ("image", "imageUrl", "thumbnail", "thumbnailUrl", "img")
_URL_KEYS = ("url", "productUrl", "link", "canonicalUrl", "detailUrl")
_BRAND_KEYS = ("brand", "brandName", "marca")
_ID_KEYS = ("id", "productId", "sku", "itemId", "USItemId", "ip")


def _first(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return None


def _extract_price(value: Any) -> float:
    if isinstance(value, dict):
        for key in ("value", "amount", "price", "lowPrice", "min"):
            if key in value:
                return _as_float(value[key])
    return _as_float(value)


def _find_product_list(data: Any) -> list[dict[str, Any]]:
    """Busca, de forma tolerante, la lista de productos dentro de respuestas
    JSON con estructuras variadas (Walmart Glass / acuenta)."""
    if isinstance(data, list):
        return [p for p in data if isinstance(p, dict)]
    if not isinstance(data, dict):
        return []
    for key in ("products", "items", "results", "records", "productList"):
        value = data.get(key)
        if isinstance(value, list) and value:
            return [p for p in value if isinstance(p, dict)]
    # busqueda recursiva superficial
    for value in data.values():
        if isinstance(value, (dict, list)):
            found = _find_product_list(value)
            if found:
                return found
    return []


def _normalize_product(product: dict[str, Any], store: dict[str, Any], position: int) -> dict[str, Any]:
    source = store["source"]
    host = store["host"]
    store_label = store.get("store_label") or source.title()

    pid = str(_first(product, _ID_KEYS) or position).strip()
    title = str(_first(product, _NAME_KEYS) or "").strip()
    brand = str(_first(product, _BRAND_KEYS) or "").strip()
    image = str(_first(product, _IMAGE_KEYS) or "")
    if isinstance(_first(product, _IMAGE_KEYS), dict):
        image = str(_first(product, _IMAGE_KEYS).get("url") or "")

    link = str(_first(product, _URL_KEYS) or "").strip()
    if link and not link.startswith("http"):
        link = f"{host}/{link.lstrip('/')}"
    if not link:
        link = f"{host}/"

    price = _extract_price(_first(product, _PRICE_KEYS))
    list_price = _extract_price(_first(product, _LIST_PRICE_KEYS))

    discount = 0
    if list_price > price > 0:
        discount = max(0, min(100, round((list_price - price) * 100 / list_price)))

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
        "category": "",
        "discount_percent": discount,
        "available": True,
        "position": position,
        "source": source,
    }


def _collect_acuenta_browser(
    store: dict[str, Any],
    query: str,
    category_id: str,
    category: dict[str, Any] | None,
    limit: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001
        return [], {"warning": f"acuenta requiere Playwright: {exc}"}

    host = store["host"]
    if query:
        url = f"{host}/search?name={urllib.parse.quote(query)}"
    else:
        url = f"{host}/ca/{category_id.strip('/')}"

    raw_products: list[dict[str, Any]] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(locale="es-CL")
            page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            page.locator('[data-consumer="productCard"][data-product-sku]').first.wait_for(timeout=30_000)
            for _ in range(4):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(500)
            raw_products = page.locator('[data-consumer="productCard"][data-product-sku]').evaluate_all(
                """cards => cards.map(card => {
                    const link = card.querySelector('a.containerCard');
                    const image = card.querySelector('[data-testid="product-image-main"] img');
                    const price = card.querySelector('[data-testid="card-base-price"]');
                    const text = (card.textContent || '').replace(/\\s+/g, ' ').trim();
                    const original = text.match(/\\(\\s*(\\$\\s*[\\d.]+)\\s*\\)/);
                    return {
                      id: card.getAttribute('data-product-sku') || '',
                      title: image?.getAttribute('alt') || card.querySelector('[data-testid="card-name"]')?.textContent || '',
                      priceText: price?.textContent || '',
                      originalPriceText: original?.[1] || '',
                      text,
                      image: image?.getAttribute('src') || '',
                      url: link?.href || ''
                    };
                })"""
            )
            browser.close()
    except Exception as exc:  # noqa: BLE001
        return [], {"search_url": url, "warning": f"acuenta: fallo Playwright ({exc})."}

    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for product in raw_products:
        sku = str(product.get("id") or "")
        if not sku or sku in seen:
            continue
        seen.add(sku)
        price = _parse_clp_text(product.get("priceText"))
        list_price = _parse_clp_text(product.get("originalPriceText")) or price
        normalized = _normalize_product(
            {
                "id": sku,
                "title": product.get("title"),
                "price": price,
                "listPrice": list_price,
                "image": product.get("image"),
                "url": product.get("url"),
            },
            store,
            len(items) + 1,
        )
        normalized["category"] = category.get("name") if category else ""
        if normalized["title"] and normalized["price"] > 0:
            items.append(normalized)
        if len(items) >= limit:
            break
    return items, {"search_url": url, "fetched_raw": len(raw_products)}


def collect_results(
    store: dict[str, Any],
    query: str = "",
    limit: int = 80,
    scan_scope: str = "complete",
    max_pages: int = 0,
    **kwargs: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    started = time.perf_counter()
    source = store["source"]
    host = store["host"]
    category_id = str(kwargs.get("category_id") or "").strip()
    cleaned_query = (query or "").strip()
    category = _configured_category_by_id(store, category_id)

    target = max(1, min(int(limit or 80), 5000))

    base_meta = {
        "source": source,
        "store": store.get("store_label") or source,
        "category_id": category_id,
        "category": category.get("name") if category else "",
        "effective_query": cleaned_query,
        "query_mode": "walmart_json",
    }

    if not category_id and not cleaned_query:
        base_meta.update({"total": 0, "total_matches": 0, "error": "empty_query",
                          "elapsed_seconds": round(time.perf_counter() - started, 2)})
        return [], base_meta

    if store.get("browser_fetch"):
        items, browser_meta = _collect_acuenta_browser(store, cleaned_query, category_id, category, target)
        base_meta.update(browser_meta)
        base_meta.update({
            "query_mode": "playwright",
            "total": len(items),
            "total_matches": len(items),
            "elapsed_seconds": round(time.perf_counter() - started, 2),
        })
        return items, base_meta

    template = (
        os.environ.get(store.get("api_env", ""))
        or store.get("api_template")
        or ""
    )
    if not template:
        base_meta.update({
            "total": 0,
            "total_matches": 0,
            "warning": (
                f"{store.get('store_label') or source}: endpoint de catalogo no "
                f"configurado. Define la variable de entorno "
                f"{store.get('api_env')} con el template del endpoint JSON "
                f"(ver Paso 1 del plan) o usa el fallback Playwright."
            ),
            "elapsed_seconds": round(time.perf_counter() - started, 2),
        })
        return [], base_meta

    url = template.format(
        host=host,
        category=urllib.parse.quote(category_id),
        query=urllib.parse.quote(cleaned_query),
        limit=target,
        page=1,
    )

    try:
        data = _fetch_json(url, host)
    except Exception as exc:  # noqa: BLE001
        base_meta.update({
            "total": 0,
            "total_matches": 0,
            "error": str(exc),
            "warning": f"{store.get('store_label') or source}: fallo la peticion al endpoint ({exc}).",
            "search_url": url,
            "elapsed_seconds": round(time.perf_counter() - started, 2),
        })
        return [], base_meta

    raw_products = _find_product_list(data)
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for product in raw_products:
        normalized = _normalize_product(product, store, len(items) + 1)
        key = normalized["id"]
        if key in seen:
            continue
        seen.add(key)
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
        base_meta["warning"] = (
            f"{store.get('store_label') or source}: la respuesta no contenia "
            f"productos reconocibles. Ajusta el parser/endpoint (Paso 1)."
        )
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

from __future__ import annotations

import json
import os
import random
import re
import threading
import time
import urllib.parse
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any


SCRAPER_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRAPER_DIR)
BASE_URL = os.getenv("ALIEXPRESS_BASE_URL", "https://www.aliexpress.com")
SEARCH_URL = f"{BASE_URL}/w/wholesale-{{query}}.html"
COOKIE_VALUE = "site=glo&c_tp=CLP&region=CL&b_locale=es_CL"
USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    ),
]
USD_CIF_THRESHOLD = 500.0
IVA_RATE = 0.19
DUTY_RATE = 0.06
HANDLING_FEE_CLP = 15_000
DEFAULT_USD_CLP_RATE = float(os.getenv("ALIEXPRESS_USD_CLP_RATE", "950"))
DEFAULT_TIMEOUT_MS = 30_000
DEFAULT_COOKIE_FILES = [
    os.path.join(SCRAPER_DIR, "aliexpress_cookies.txt"),
    os.path.join(ROOT_DIR, "aliexpress_cookies.txt"),
]
CHALLENGE_COOLDOWN_SECONDS = max(30, int(os.getenv("ALIEXPRESS_CHALLENGE_COOLDOWN_SECONDS", "180")))
_CHALLENGE_LOCK = threading.Lock()
_CHALLENGE_UNTIL = 0.0
_SESSION_COOKIE_LOCK = threading.Lock()
_SESSION_COOKIES: list[dict[str, Any]] = []

ALIEXPRESS_CATEGORY_TREE = [
    ("electronics", "Electronica", "electronics", [
        ("phones", "Telefonos y accesorios", "phone case charger smartphone"),
        ("audio", "Audio y auriculares", "earphones headphones speaker microphone"),
        ("smart_electronics", "Electronica inteligente", "smart watch smart home camera"),
        ("components", "Componentes electronicos", "electronic components module sensor"),
    ]),
    ("computers", "Computacion y oficina", "computer laptop keyboard mouse monitor", [
        ("laptops", "Laptops y tablets", "laptop tablet notebook"),
        ("computer_peripherals", "Teclados, mouse y perifericos", "keyboard mouse gamer mechanical"),
        ("storage", "Almacenamiento", "ssd hdd usb flash drive memory card"),
        ("networking", "Redes", "wifi router network adapter switch"),
        ("printers", "Impresoras y oficina", "printer label scanner office"),
    ]),
    ("automotive", "Automocion", "automotive car motorcycle", [
        ("car_electronics", "Electronica para auto", "car camera dashcam android radio"),
        ("motorcycle", "Motocicletas", "motorcycle accessories helmet gloves"),
        ("car_parts", "Repuestos y accesorios", "car accessories parts tools"),
    ]),
    ("home_garden", "Casa y jardin", "home garden kitchen decor", [
        ("kitchen", "Cocina", "kitchen tools cookware"),
        ("home_decor", "Decoracion", "home decor led light wall"),
        ("garden", "Jardin", "garden irrigation plant tools"),
        ("storage_home", "Organizacion", "storage organizer shelf box"),
    ]),
    ("fashion_women", "Moda mujer", "women clothing fashion", [
        ("women_clothing", "Ropa de mujer", "women clothing dress blouse"),
        ("women_accessories", "Accesorios mujer", "women accessories scarf belt"),
        ("lingerie", "Ropa interior", "lingerie underwear women"),
    ]),
    ("fashion_men", "Moda hombre", "men clothing fashion", [
        ("men_clothing", "Ropa de hombre", "men clothing shirt pants"),
        ("men_accessories", "Accesorios hombre", "men accessories wallet belt"),
        ("mens_underwear", "Ropa interior hombre", "men underwear socks"),
    ]),
    ("shoes_bags", "Zapatos y bolsos", "shoes bags", [
        ("shoes", "Zapatos", "shoes sneakers boots"),
        ("bags", "Bolsos y mochilas", "bag backpack handbag"),
        ("luggage", "Equipaje", "luggage suitcase travel bag"),
    ]),
    ("beauty_health", "Belleza y salud", "beauty health", [
        ("makeup", "Maquillaje", "makeup cosmetics"),
        ("skin_care", "Cuidado de piel", "skin care beauty"),
        ("hair", "Cabello", "hair clipper dryer wig"),
        ("health", "Salud y cuidado personal", "health personal care massager"),
    ]),
    ("sports_outdoors", "Deportes y aire libre", "sports outdoors", [
        ("fitness", "Fitness", "fitness gym equipment"),
        ("cycling", "Ciclismo", "cycling bike accessories"),
        ("camping", "Camping", "camping hiking outdoor"),
        ("fishing", "Pesca", "fishing tackle reel"),
    ]),
    ("toys_games", "Juguetes y juegos", "toys games", [
        ("toys", "Juguetes", "toys kids"),
        ("rc", "RC y drones", "rc car drone"),
        ("puzzles", "Puzzles y juegos", "puzzle board game"),
    ]),
    ("mother_kids", "Mama y bebe", "baby kids", [
        ("baby", "Bebe", "baby clothes stroller"),
        ("kids_clothing", "Ropa infantil", "kids clothing shoes"),
        ("maternity", "Maternidad", "maternity pregnancy"),
    ]),
    ("tools", "Herramientas", "tools", [
        ("power_tools", "Herramientas electricas", "power tools drill grinder"),
        ("hand_tools", "Herramientas manuales", "hand tools screwdriver wrench"),
        ("measurement", "Medicion", "multimeter laser measure"),
    ]),
    ("appliances", "Electrodomesticos", "appliances", [
        ("small_appliances", "Pequenos electrodomesticos", "small appliances blender vacuum"),
        ("home_appliances", "Electrodomesticos hogar", "home appliances"),
        ("personal_appliances", "Cuidado personal electrico", "electric shaver hair dryer"),
    ]),
    ("jewelry", "Joyeria y relojes", "jewelry watches", [
        ("watches", "Relojes", "watch smartwatch"),
        ("jewelry_accessories", "Joyeria", "jewelry necklace ring bracelet"),
        ("beads", "Bisuteria e insumos", "beads charms jewelry making"),
    ]),
    ("pet_supplies", "Mascotas", "pet supplies", [
        ("dog_supplies", "Perros", "dog pet supplies"),
        ("cat_supplies", "Gatos", "cat pet supplies"),
        ("aquarium", "Acuario", "aquarium fish tank"),
    ]),
]


def _format_clp(value: float) -> str:
    amount = max(0, int(round(value)))
    return f"$ {amount:,}".replace(",", ".")


def _clean_number(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    text = re.sub(r"[^\d,.-]", "", text)
    if not text:
        return 0.0
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif text.count(".") > 1:
        text = text.replace(".", "")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _first_value(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return None


def fetch_categories() -> list[dict[str, Any]]:
    categories: list[dict[str, Any]] = []
    for root_id, root_name, root_search, children in ALIEXPRESS_CATEGORY_TREE:
        categories.append({
            "id": root_id,
            "value": root_id,
            "label": root_name,
            "name": root_name,
            "search": root_search,
            "depth": 0,
            "parent_id": "",
            "has_children": bool(children),
        })
        for child_id, child_name, child_search in children:
            categories.append({
                "id": child_id,
                "value": child_id,
                "label": f"{root_name} / {child_name}",
                "name": child_name,
                "search": child_search,
                "depth": 1,
                "parent_id": root_id,
                "has_children": False,
            })
    return categories


def _category_by_id(category_id: str | None) -> dict[str, Any] | None:
    wanted = str(category_id or "").strip()
    if not wanted:
        return None
    return next((category for category in fetch_categories() if category.get("id") == wanted), None)


def _category_seed(category_id: str | None) -> str:
    category = _category_by_id(category_id)
    if not category:
        return ""
    return str(category.get("search") or category.get("name") or "").strip()


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _extract_balanced_object(text: str, start: int) -> str:
    depth = 0
    in_string = False
    quote = ""
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                in_string = False
            continue
        if char in {'"', "'"}:
            in_string = True
            quote = char
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    return ""


def _extract_assigned_json(html: str, marker: str) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    search_from = 0
    while True:
        marker_index = html.find(marker, search_from)
        if marker_index < 0:
            break
        brace_index = html.find("{", marker_index)
        if brace_index < 0:
            break
        raw = _extract_balanced_object(html, brace_index)
        if raw:
            try:
                loaded = json.loads(raw)
            except json.JSONDecodeError:
                loaded = None
            if isinstance(loaded, dict):
                objects.append(loaded)
        search_from = max(brace_index + 1, marker_index + len(marker))
    return objects


def _extract_keyed_object(html: str, key: str) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    search_from = 0
    marker = f'"{key}"'
    while True:
        marker_index = html.find(marker, search_from)
        if marker_index < 0:
            break
        colon_index = html.find(":", marker_index)
        brace_index = html.find("{", colon_index)
        if colon_index < 0 or brace_index < 0:
            break
        raw = _extract_balanced_object(html, brace_index)
        if raw:
            try:
                loaded = json.loads(raw)
            except json.JSONDecodeError:
                loaded = None
            if isinstance(loaded, dict):
                objects.append({key: loaded})
        search_from = max(brace_index + 1, marker_index + len(marker))
    return objects


def _extract_json_objects(html: str) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for marker in ("window.runParams", "window.__AER_DATA__", "window._dida_config_", "window._d_c_.DCData"):
        objects.extend(_extract_assigned_json(html, marker))
    objects.extend(_extract_keyed_object(html, "itemList"))

    for match in re.finditer(
        r'<script[^>]+type=["\']application/json["\'][^>]*>(.*?)</script>',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    ):
        raw = match.group(1).strip()
        if not raw:
            continue
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, dict):
            objects.append(loaded)
    return objects


def _looks_like_product(node: dict[str, Any]) -> bool:
    has_id = any(key in node for key in ("productId", "product_id", "itemId", "id"))
    has_title = any(key in node for key in ("title", "productTitle", "subject", "name"))
    has_price = any(key in node for key in ("price", "prices", "salePrice", "minPrice", "formattedPrice", "priceInfo"))
    return has_id and has_title and has_price


def _product_nodes(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for payload in payloads:
        for node in _walk(payload):
            if not _looks_like_product(node):
                continue
            product_id = str(_first_value(node, ("productId", "product_id", "itemId", "id")) or "").strip()
            if not product_id or product_id in seen_ids:
                continue
            seen_ids.add(product_id)
            products.append(node)
    return products


def _extract_price_amount(value: Any) -> tuple[float, str]:
    if isinstance(value, dict):
        amount = _first_value(value, ("value", "amount", "minPrice", "salePrice", "price", "cent"))
        currency = str(_first_value(value, ("currency", "currencyCode", "symbol", "currencyCodeSymbol")) or "").upper()
        parsed = _clean_number(amount)
        if parsed > 0:
            return parsed, currency
    parsed = _clean_number(value)
    if parsed > 0:
        text = str(value or "").upper()
        currency = "USD" if "US" in text or "USD" in text else ("CLP" if "$" in text or "CLP" in text else "")
        return parsed, currency
    return 0.0, ""


def _price_from_node(node: dict[str, Any]) -> tuple[float, str, float]:
    price_info = node.get("priceInfo") if isinstance(node.get("priceInfo"), dict) else {}
    prices = node.get("prices") if isinstance(node.get("prices"), dict) else {}
    sale_price = prices.get("salePrice") if isinstance(prices.get("salePrice"), dict) else {}
    original_price = prices.get("originalPrice") if isinstance(prices.get("originalPrice"), dict) else {}
    for price_dict in (sale_price, original_price):
        parsed = _clean_number(_first_value(price_dict, ("minPrice", "cent", "value", "amount")))
        max_price = _clean_number(_first_value(price_dict, ("maxPrice", "maxAmount", "maxCent")))
        currency = str(_first_value(price_dict, ("currencyCode", "currency", "symbol")) or "").upper()
        if parsed > 0:
            return parsed, currency, max_price
    candidates = [
        sale_price.get("formattedPrice"),
        price_info.get("salePrice"),
        price_info.get("formattedPrice"),
        price_info.get("minPrice"),
        price_info.get("price"),
        original_price.get("formattedPrice"),
        node.get("salePrice"),
        node.get("minPrice"),
        node.get("price"),
        node.get("formattedPrice"),
    ]
    for candidate in candidates:
        parsed, currency = _extract_price_amount(candidate)
        if parsed > 0:
            max_price = _clean_number(_first_value(candidate, ("maxPrice", "maxAmount", "maxCent"))) if isinstance(candidate, dict) else 0.0
            return parsed, currency, max_price
    return 0.0, "", 0.0


def _variant_info_from_node(node: dict[str, Any], base_price: float, currency: str) -> dict[str, Any]:
    variant_keys = {
        "sku",
        "skuid",
        "skus",
        "skuinfo",
        "skuinfos",
        "skulist",
        "skuimages",
        "skuimageslist",
        "sku_images",
        "skuproperties",
        "skupropertieslist",
        "skuattr",
        "aeskupropertydtos",
    }
    price_values: list[float] = []
    detected_keys = 0
    variant_count = 0

    for candidate in _walk(node):
        for key, value in candidate.items():
            normalized_key = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if normalized_key in variant_keys or normalized_key.startswith("sku"):
                detected_keys += 1
                if isinstance(value, list):
                    variant_count = max(variant_count, len(value))
                elif isinstance(value, dict):
                    variant_count = max(variant_count, len(value))

            if any(token in normalized_key for token in ("price", "amount", "cent")):
                parsed, parsed_currency = _extract_price_amount(value)
                if parsed > 0 and (not parsed_currency or not currency or parsed_currency == currency):
                    price_values.append(parsed)
                if isinstance(value, dict):
                    for nested_key in ("minPrice", "maxPrice", "salePrice", "price", "amount", "value", "cent"):
                        parsed = _clean_number(value.get(nested_key))
                        if parsed > 0:
                            price_values.append(parsed)

    reasonable_prices = [
        value
        for value in price_values
        if value > 0 and (base_price <= 0 or 0.2 * base_price <= value <= 10 * base_price)
    ]
    if base_price > 0:
        reasonable_prices.append(base_price)
    min_price = min(reasonable_prices) if reasonable_prices else base_price
    max_price = max(reasonable_prices) if reasonable_prices else base_price
    has_range = bool(base_price > 0 and max_price > base_price * 1.03)

    return {
        "has_variants": detected_keys > 0 or variant_count > 1 or has_range,
        "variant_count": variant_count if variant_count > 1 else None,
        "variant_price_min": min_price if min_price > 0 else None,
        "variant_price_max": max_price if max_price > min_price else None,
        "variant_price_range_raw": [min_price, max_price] if max_price > min_price else None,
    }


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.values())
    return []


def _normalize_sku_token(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if ":" in text:
        return text.split(":")[-1].strip()
    return text


def _sku_property_maps(sku_module: dict[str, Any]) -> tuple[dict[str, dict[str, str]], int]:
    property_lists = []
    for key in (
        "skuPropertyList",
        "productSKUPropertyList",
        "skuProperties",
        "skuProps",
        "skuPropertyJson",
        "aeSkuPropertyDtos",
    ):
        property_lists.extend(item for item in _as_list(sku_module.get(key)) if isinstance(item, dict))

    value_map: dict[str, dict[str, str]] = {}
    property_count = 0
    for prop in property_lists:
        prop_name = str(_first_value(prop, ("skuPropertyName", "propertyName", "name", "title")) or "").strip()
        values = []
        for key in ("skuPropertyValues", "skuPropertyValueList", "values", "propertyValues", "skuValues"):
            values.extend(item for item in _as_list(prop.get(key)) if isinstance(item, dict))
        if values:
            property_count += 1
        for value in values:
            value_name = str(
                _first_value(value, ("skuPropertyValueName", "propertyValueName", "name", "value", "title", "text"))
                or ""
            ).strip()
            image = _absolute_url(
                _first_value(value, ("skuPropertyImagePath", "skuPropertyImage", "image", "imageUrl", "imgUrl"))
            )
            ids = [
                value.get("propertyValueIdLong"),
                value.get("propertyValueId"),
                value.get("skuPropertyValueId"),
                value.get("vid"),
                value.get("id"),
            ]
            for raw_id in ids:
                token = _normalize_sku_token(raw_id)
                if token:
                    value_map[token] = {"property": prop_name, "value": value_name, "image": image}
    return value_map, property_count


def _sku_price_entries(sku_module: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for key in ("skuPriceList", "skuPrices", "skuList", "skuValList", "priceList"):
        entries.extend(item for item in _as_list(sku_module.get(key)) if isinstance(item, dict))
    return entries


def _sku_entry_price(entry: dict[str, Any]) -> tuple[float, str]:
    candidates: list[Any] = []
    sku_val = entry.get("skuVal") if isinstance(entry.get("skuVal"), dict) else {}
    candidates.extend([
        sku_val.get("skuActivityAmount"),
        sku_val.get("skuAmount"),
        sku_val.get("actSkuCalPrice"),
        sku_val.get("skuCalPrice"),
        sku_val.get("skuPrice"),
        entry.get("salePrice"),
        entry.get("price"),
        entry.get("amount"),
        entry.get("skuActivityAmount"),
        entry.get("skuAmount"),
        entry.get("skuCalPrice"),
    ])
    for candidate in candidates:
        parsed, currency = _extract_price_amount(candidate)
        if parsed > 0:
            return parsed, currency
    return 0.0, ""


def _sku_entry_prop_tokens(entry: dict[str, Any]) -> list[str]:
    raw = _first_value(entry, ("skuPropIds", "skuPropId", "skuPropertyIds", "props", "propPath", "skuAttr"))
    if isinstance(raw, list):
        return [_normalize_sku_token(value) for value in raw if _normalize_sku_token(value)]
    text = str(raw or "")
    return [_normalize_sku_token(part) for part in re.split(r"[;,#\s]+", text) if _normalize_sku_token(part)]


def _extract_variant_details_from_payloads(
    payloads: list[dict[str, Any]],
    shipping: float,
    fallback_currency: str,
    usd_clp_rate: float,
    price_includes_chile_vat: bool,
    is_choice: bool,
) -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []
    seen: set[str] = set()

    for node in _walk(payloads):
        if not isinstance(node, dict):
            continue
        sku_module = node.get("skuModule") if isinstance(node.get("skuModule"), dict) else node
        sku_entries = _sku_price_entries(sku_module)
        if not sku_entries:
            continue
        value_map, property_count = _sku_property_maps(sku_module)
        for entry in sku_entries:
            price, currency = _sku_entry_price(entry)
            if price <= 0:
                continue
            tokens = _sku_entry_prop_tokens(entry)
            parts: list[str] = []
            image = ""
            for token in tokens:
                mapped = value_map.get(token)
                if not mapped:
                    continue
                label = mapped["value"]
                if mapped["property"]:
                    label = f"{mapped['property']}: {label}" if label else mapped["property"]
                if label:
                    parts.append(label)
                if not image and mapped.get("image"):
                    image = mapped["image"]
            variant_name = " / ".join(dict.fromkeys(parts)) or str(_first_value(entry, ("skuName", "name", "title")) or "").strip()
            sku_id = str(_first_value(entry, ("skuId", "id", "skuAttr")) or ",".join(tokens) or variant_name).strip()
            key = sku_id or variant_name
            if not key or key in seen:
                continue
            seen.add(key)
            cost = _calculate_chile_cost(price + shipping, currency or fallback_currency, usd_clp_rate, price_includes_chile_vat, is_choice=is_choice)
            variants.append({
                "sku_id": sku_id,
                "name": variant_name,
                "attributes": parts,
                "price_original": price,
                "shipping": shipping,
                "display_currency": currency or fallback_currency or "CLP",
                "price_final_clp": float(cost["final_price_clp"]),
                "price_clp_final": float(cost["final_price_clp"]),
                "tax_estimated_clp": round(_to_clp(float(cost["tax_applied_usd"]) + float(cost["handling_fee_usd"]), usd_clp_rate)),
                "final_price_usd": float(cost["final_price_usd"]),
                "image": image or None,
                "available": not bool(entry.get("disabled") or entry.get("soldOut")),
                "stock": _clean_number(_first_value(entry, ("availQuantity", "stock", "quantity"))),
            })
        if variants and (property_count > 0 or len(variants) > 1):
            break

    variants.sort(key=lambda item: (item["price_final_clp"], item.get("name") or ""))
    return variants


def _shipping_from_node(node: dict[str, Any], currency: str) -> float:
    shipping = node.get("shipping") if isinstance(node.get("shipping"), dict) else {}
    candidates = [
        shipping.get("shippingFee"),
        shipping.get("freightAmount"),
        node.get("shippingFee"),
        node.get("freightAmount"),
    ]
    for candidate in candidates:
        if isinstance(candidate, dict):
            parsed = _clean_number(_first_value(candidate, ("value", "amount", "fee")))
        else:
            parsed = _clean_number(candidate)
        if parsed > 0:
            return parsed
    shipping_text = " ".join(str(v) for v in shipping.values()) if shipping else str(node.get("shippingText") or "")
    if re.search(r"free|gratis|env[ií]o\s+gratis", shipping_text, flags=re.IGNORECASE):
        return 0.0
    return 0.0


def _to_usd(amount: float, currency: str, usd_clp_rate: float) -> float:
    currency = (currency or "").upper()
    if currency in {"CLP", "$", "CL"} or amount > 10_000:
        return amount / usd_clp_rate
    return amount


def _to_clp(amount_usd: float, usd_clp_rate: float) -> float:
    return amount_usd * usd_clp_rate


def _calculate_chile_cost(
    display_total: float,
    currency: str,
    usd_clp_rate: float,
    price_includes_chile_vat: bool,
    is_choice: bool = False,
) -> dict[str, float | bool]:
    display_total_usd = _to_usd(display_total, currency, usd_clp_rate)
    if display_total_usd <= 0:
        return {
            "original_price_usd": 0.0,
            "tax_applied_usd": 0.0,
            "final_price_usd": 0.0,
            "final_price_clp": 0.0,
            "duty_applied_usd": 0.0,
            "iva_applied_usd": 0.0,
            "handling_fee_usd": 0.0,
            "over_usd_500": False,
        }

    effectively_includes_vat = price_includes_chile_vat or is_choice

    if display_total_usd <= USD_CIF_THRESHOLD:
        if effectively_includes_vat:
            net_cif_usd = display_total_usd / (1 + IVA_RATE)
            iva_usd = display_total_usd - net_cif_usd
            final_usd = display_total_usd
        else:
            net_cif_usd = display_total_usd
            iva_usd = net_cif_usd * IVA_RATE
            final_usd = net_cif_usd + iva_usd
        duty_usd = 0.0
        handling_usd = 0.0
    else:
        # For values over USD 500, customs applies duty and VAT over CIF. If the
        # Chilean AliExpress price already includes VAT, back it out first to avoid
        # counting the same IVA twice in the final estimate.
        net_cif_usd = display_total_usd / (1 + IVA_RATE) if effectively_includes_vat else display_total_usd
        duty_usd = net_cif_usd * DUTY_RATE
        iva_usd = (net_cif_usd + duty_usd) * IVA_RATE
        handling_usd = HANDLING_FEE_CLP / usd_clp_rate
        final_usd = net_cif_usd + duty_usd + iva_usd + handling_usd

    return {
        "original_price_usd": round(net_cif_usd, 2),
        "tax_applied_usd": round(duty_usd + iva_usd, 2),
        "final_price_usd": round(final_usd, 2),
        "final_price_clp": round(_to_clp(final_usd, usd_clp_rate)),
        "duty_applied_usd": round(duty_usd, 2),
        "iva_applied_usd": round(iva_usd, 2),
        "handling_fee_usd": round(handling_usd, 2),
        "over_usd_500": display_total_usd > USD_CIF_THRESHOLD,
    }


def _absolute_url(value: Any) -> str:
    if not value:
        return ""
    url = str(value).strip()
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/"):
        return f"{BASE_URL}{url}"
    return f"{BASE_URL}/{url}"


def _cookie_expiry(value: str) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        if value.isdigit():
            number = int(value)
            return number // 1000 if number > 10_000_000_000 else number
        from datetime import datetime

        normalized = value.replace("Z", "+00:00")
        return int(datetime.fromisoformat(normalized).timestamp())
    except Exception:
        return None


def _cookie_from_parts(parts: list[str]) -> dict[str, Any] | None:
    if len(parts) < 2:
        return None
    name = parts[0].strip()
    value = parts[1].strip()
    if not name or not value:
        return None

    domain = parts[2].strip() if len(parts) > 2 and parts[2].strip() else ".aliexpress.com"
    path = parts[3].strip() if len(parts) > 3 and parts[3].strip() else "/"
    cookie: dict[str, Any] = {
        "name": name,
        "value": value,
        "domain": domain,
        "path": path,
        "secure": True,
        "httpOnly": False,
        "sameSite": "Lax",
    }
    expires = _cookie_expiry(parts[4]) if len(parts) > 4 else None
    if expires:
        cookie["expires"] = expires
    return cookie


def _parse_cookie_file(path: str) -> list[dict[str, Any]]:
    try:
        raw = open(path, "r", encoding="utf-8").read()
    except FileNotFoundError:
        return []

    stripped = raw.strip()
    if not stripped:
        return []

    cookies: list[dict[str, Any]] = []
    try:
        loaded = json.loads(stripped)
    except json.JSONDecodeError:
        loaded = None
    if isinstance(loaded, list):
        for item in loaded:
            if not isinstance(item, dict) or not item.get("name") or not item.get("value"):
                continue
            cookie = {
                "name": str(item.get("name")),
                "value": str(item.get("value")),
                "domain": str(item.get("domain") or ".aliexpress.com"),
                "path": str(item.get("path") or "/"),
                "secure": bool(item.get("secure", True)),
                "httpOnly": bool(item.get("httpOnly", False)),
                "sameSite": item.get("sameSite") if item.get("sameSite") in {"Strict", "Lax", "None"} else "Lax",
            }
            expires = item.get("expires") or item.get("expirationDate")
            if expires:
                cookie["expires"] = int(float(expires))
            cookies.append(cookie)
        return cookies

    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "\t" in line:
            cookie = _cookie_from_parts(line.split("\t"))
            if cookie:
                cookies.append(cookie)
            continue
        for part in line.split(";"):
            if "=" not in part:
                continue
            name, value = part.split("=", 1)
            cookie = _cookie_from_parts([name.strip(), value.strip(), ".aliexpress.com", "/"])
            if cookie:
                cookies.append(cookie)
    return cookies


def _load_cookies(cookie_file: str | None = None) -> list[dict[str, Any]]:
    paths = []
    explicit = cookie_file or os.getenv("ALIEXPRESS_COOKIE_FILE")
    if explicit:
        paths.append(explicit)
    paths.extend(DEFAULT_COOKIE_FILES)

    seen: set[tuple[str, str, str]] = set()
    cookies: list[dict[str, Any]] = []
    for path in paths:
        for cookie in _parse_cookie_file(path):
            key = (cookie["name"], cookie.get("domain", ""), cookie.get("path", "/"))
            if key in seen:
                continue
            seen.add(key)
            cookies.append(cookie)
    return cookies


def _browser_cookies(cookie_file: str | None = None) -> list[dict[str, Any]]:
    cookies = _load_cookies(cookie_file)
    with _SESSION_COOKIE_LOCK:
        session_cookies = [dict(cookie) for cookie in _SESSION_COOKIES]
    by_key = {
        (cookie["name"], cookie.get("domain", ""), cookie.get("path", "/")): cookie
        for cookie in cookies
    }
    for cookie in session_cookies:
        key = (cookie["name"], cookie.get("domain", ""), cookie.get("path", "/"))
        by_key[key] = cookie
    return list(by_key.values())


def _remember_session_cookies(cookies: list[dict[str, Any]]) -> None:
    with _SESSION_COOKIE_LOCK:
        _SESSION_COOKIES.clear()
        _SESSION_COOKIES.extend(dict(cookie) for cookie in cookies)


def _discount_from_node(node: dict[str, Any]) -> int:
    prices = node.get("prices") if isinstance(node.get("prices"), dict) else {}
    sale_price = prices.get("salePrice") if isinstance(prices.get("salePrice"), dict) else {}
    if sale_price.get("discount") is not None:
        return max(0, min(100, int(round(_clean_number(sale_price.get("discount"))))))
    value = _first_value(node, ("discount", "discountPercent", "discount_percentage", "discountRate"))
    parsed = _clean_number(value)
    if parsed <= 0:
        return 0
    return max(0, min(100, int(round(parsed))))


def _normalize_product(
    node: dict[str, Any],
    position: int,
    usd_clp_rate: float,
    price_includes_chile_vat: bool,
) -> dict[str, Any]:
    product_id = str(_first_value(node, ("productId", "product_id", "itemId", "id")) or position).strip()
    title_value = _first_value(node, ("title", "productTitle", "subject", "name"))
    if isinstance(title_value, dict):
        title_value = _first_value(title_value, ("displayTitle", "seoTitle", "title", "text"))
    title = str(title_value or "").strip()
    price, currency, max_price = _price_from_node(node)
    variant_info = _variant_info_from_node(node, price, currency)
    variant_max_price = _clean_number(variant_info.get("variant_price_max"))
    if variant_max_price > max_price:
        max_price = variant_max_price

    is_choice = False
    selling_points = node.get("sellingPoints", [])
    if isinstance(selling_points, list):
        for sp in selling_points:
            if isinstance(sp, dict):
                marker = " ".join(str(sp.get(key, "")) for key in ("source", "tagText", "title", "text")).lower()
                if "choice" in marker:
                    is_choice = True
                    break
    if not is_choice:
        trace = node.get("trace") if isinstance(node.get("trace"), dict) else {}
        ut_log_map = trace.get("utLogMap") if isinstance(trace.get("utLogMap"), dict) else {}
        raw_choice = _first_value(node, ("isChoice", "choice", "is_choice"))
        is_choice = str(ut_log_map.get("isChoice") or raw_choice or "").lower() == "true"

    shipping = _shipping_from_node(node, currency)
    display_total = price + shipping
    cost = _calculate_chile_cost(display_total, currency, usd_clp_rate, price_includes_chile_vat, is_choice=is_choice)
    max_price_clp = 0.0
    if max_price > price:
        max_cost = _calculate_chile_cost(max_price + shipping, currency, usd_clp_rate, price_includes_chile_vat, is_choice=is_choice)
        max_price_clp = float(max_cost["final_price_clp"])

    url = _absolute_url(_first_value(node, ("productDetailUrl", "productUrl", "url", "link")))
    if not url and product_id:
        url = f"{BASE_URL}/item/{product_id}.html"

    image_value = _first_value(node, ("imageUrl", "productImage", "imgUrl", "image"))
    if isinstance(image_value, dict):
        image_value = _first_value(image_value, ("imgUrl", "url", "imageUrl"))
    image = _absolute_url(image_value)
    brand = _first_value(node, ("brand", "brandName"))
    category = _first_value(node, ("category", "categoryName"))
    tax_estimated_usd = float(cost["tax_applied_usd"]) + float(cost["handling_fee_usd"])
    tax_estimated_clp = round(_to_clp(tax_estimated_usd, usd_clp_rate))

    return {
        "id": f"aliexpress#{product_id}",
        "title": title,
        "name": title,
        "price": float(cost["final_price_clp"]),
        "price_clp_final": float(cost["final_price_clp"]),
        "price_final_clp": float(cost["final_price_clp"]),
        "formatted_price": _format_clp(float(cost["final_price_clp"])),
        "url": url,
        "link": url,
        "image": image,
        "url_imagen": image,
        "store": "AliExpress",
        "brand": str(brand).strip() if brand else None,
        "category": str(category).strip() if category else None,
        "discount_percent": _discount_from_node(node),
        "price_original": price,
        "original_price_usd": float(cost["original_price_usd"]),
        "shipping": shipping,
        "tax_applied_usd": float(cost["tax_applied_usd"]),
        "tax_estimated": tax_estimated_clp,
        "tax_estimated_clp": tax_estimated_clp,
        "tax_estimated_usd": round(tax_estimated_usd, 2),
        "final_price_usd": float(cost["final_price_usd"]),
        "display_price_raw": price,
        "display_currency": currency or "CLP",
        "shipping_raw": shipping,
        "duty_applied_usd": float(cost["duty_applied_usd"]),
        "iva_applied_usd": float(cost["iva_applied_usd"]),
        "handling_fee_usd": float(cost["handling_fee_usd"]),
        "over_usd_500": bool(cost["over_usd_500"]),
        "is_choice": is_choice,
        "has_variants": bool(variant_info["has_variants"] or max_price_clp > float(cost["final_price_clp"])),
        "variant_count": variant_info.get("variant_count"),
        "variant_price_min": variant_info.get("variant_price_min"),
        "variant_price_max": variant_info.get("variant_price_max"),
        "variant_price_range_raw": variant_info.get("variant_price_range_raw"),
        "max_price_clp": max_price_clp if max_price_clp > 0 else None,
        "position": position,
        "source": "aliexpress",
    }


def _stealth_page(page: Any) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            from playwright_stealth import stealth_sync
        except ImportError:
            return
        stealth_sync(page)


def _fetch_search_html(query: str, page_num: int, cookie_file: str | None = None) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "AliExpress requiere playwright y playwright-stealth. Instala dependencias y ejecuta: playwright install chromium"
        ) from exc

    global _CHALLENGE_UNTIL
    with _CHALLENGE_LOCK:
        challenge_remaining = _CHALLENGE_UNTIL - time.monotonic()
    if challenge_remaining > 0:
        raise RuntimeError(f"AliExpress en pausa anti-bloqueo ({int(challenge_remaining)}s restantes)")

    encoded_query = urllib.parse.quote(re.sub(r"\s+", "-", query.strip()))
    bases = list(dict.fromkeys([BASE_URL, "https://www.aliexpress.com", "https://es.aliexpress.com"]))
    channels = [None, "chrome"]
    last_html = ""
    last_error: Exception | None = None
    with sync_playwright() as playwright:
        for base in bases:
            url = f"{base}/w/wholesale-{encoded_query}.html"
            if page_num > 1:
                url = f"{url}?page={page_num}"
            for channel in channels:
                launch_options: dict[str, Any] = {
                    "headless": True,
                    "args": [
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--no-sandbox",
                    ],
                }
                if channel:
                    launch_options["channel"] = channel
                proxy_server = os.getenv("ALIEXPRESS_PROXY_SERVER", "").strip()
                if proxy_server:
                    proxy: dict[str, str] = {"server": proxy_server}
                    proxy_username = os.getenv("ALIEXPRESS_PROXY_USERNAME", "").strip()
                    proxy_password = os.getenv("ALIEXPRESS_PROXY_PASSWORD", "").strip()
                    if proxy_username:
                        proxy["username"] = proxy_username
                    if proxy_password:
                        proxy["password"] = proxy_password
                    launch_options["proxy"] = proxy
                try:
                    browser = playwright.chromium.launch(**launch_options)
                except Exception as exc:
                    last_error = exc
                    continue
                try:
                    context = browser.new_context(
                        locale="es-CL",
                        timezone_id="America/Santiago",
                        viewport={"width": 1366, "height": 768},
                        user_agent=random.choice(USER_AGENTS),
                        extra_http_headers={
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                            "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
                            "Referer": base,
                            "Upgrade-Insecure-Requests": "1",
                        },
                    )
                    cookies = _browser_cookies(cookie_file)
                    cookies.append(
                        {
                            "name": "aep_usuc_f",
                            "value": COOKIE_VALUE,
                            "domain": ".aliexpress.com",
                            "path": "/",
                            "httpOnly": False,
                            "secure": True,
                            "sameSite": "Lax",
                        }
                    )
                    context.add_cookies(cookies)
                    page = context.new_page()
                    _stealth_page(page)
                    page.add_init_script(
                        """
                        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                        Object.defineProperty(navigator, 'languages', { get: () => ['es-CL', 'es', 'en'] });
                        Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
                        """
                    )
                    page.goto(url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
                    page.wait_for_timeout(random.randint(1600, 2600))
                    last_html = page.content()
                    if not _is_challenge_page(last_html):
                        _remember_session_cookies(context.cookies())
                        with _CHALLENGE_LOCK:
                            _CHALLENGE_UNTIL = 0.0
                        return last_html
                    if base == "https://www.aliexpress.com" and channel == "chrome":
                        with _CHALLENGE_LOCK:
                            _CHALLENGE_UNTIL = time.monotonic() + CHALLENGE_COOLDOWN_SECONDS
                        return last_html
                except Exception as exc:
                    last_error = exc
                finally:
                    browser.close()

    if last_html:
        return last_html
    if last_error:
        raise last_error
    raise RuntimeError("AliExpress no entrego una respuesta util.")


def _fetch_detail_html(url: str, cookie_file: str | None = None) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "AliExpress requiere playwright y playwright-stealth. Instala dependencias y ejecuta: playwright install chromium"
        ) from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        try:
            context = browser.new_context(
                locale="es-CL",
                timezone_id="America/Santiago",
                viewport={"width": 1366, "height": 768},
                user_agent=random.choice(USER_AGENTS),
                extra_http_headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
                    "Referer": BASE_URL,
                    "Upgrade-Insecure-Requests": "1",
                },
            )
            cookies = _load_cookies(cookie_file)
            cookies.append(
                {
                    "name": "aep_usuc_f",
                    "value": COOKIE_VALUE,
                    "domain": ".aliexpress.com",
                    "path": "/",
                    "httpOnly": False,
                    "secure": True,
                    "sameSite": "Lax",
                }
            )
            context.add_cookies(cookies)
            page = context.new_page()
            _stealth_page(page)
            page.goto(url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
            page.wait_for_timeout(random.randint(2200, 3600))
            return page.content()
        finally:
            browser.close()


def _extract_json_from_text(text: str) -> list[dict[str, Any]]:
    stripped = (text or "").strip()
    if not stripped:
        return []
    candidates = [stripped]
    match = re.search(r"^[\w$.]+\((.*)\)\s*;?$", stripped, flags=re.DOTALL)
    if match:
        candidates.append(match.group(1).strip())
    objects: list[dict[str, Any]] = []
    for candidate in candidates:
        try:
            loaded = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, dict):
            objects.append(loaded)
    return objects


def _fetch_detail_payloads(url: str, cookie_file: str | None = None) -> list[dict[str, Any]]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "AliExpress requiere playwright y playwright-stealth. Instala dependencias y ejecuta: playwright install chromium"
        ) from exc

    payloads: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        try:
            context = browser.new_context(
                locale="es-CL",
                timezone_id="America/Santiago",
                viewport={"width": 1366, "height": 768},
                user_agent=random.choice(USER_AGENTS),
                extra_http_headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
                    "Referer": BASE_URL,
                    "Upgrade-Insecure-Requests": "1",
                },
            )
            cookies = _load_cookies(cookie_file)
            cookies.append(
                {
                    "name": "aep_usuc_f",
                    "value": COOKIE_VALUE,
                    "domain": ".aliexpress.com",
                    "path": "/",
                    "httpOnly": False,
                    "secure": True,
                    "sameSite": "Lax",
                }
            )
            context.add_cookies(cookies)
            page = context.new_page()
            _stealth_page(page)

            def on_response(response: Any) -> None:
                response_url = str(getattr(response, "url", "") or "")
                if not any(marker in response_url for marker in ("mtop.aliexpress", "/fn/", "itemdetail", "pdp")):
                    return
                if any(marker in response_url for marker in ("/css/", "/js/", ".css", ".js", ".png", ".jpg", ".webp")):
                    return
                try:
                    text = response.text()
                except Exception:
                    return
                payloads.extend(_extract_json_from_text(text))

            page.on("response", on_response)
            page.goto(url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
            page.wait_for_timeout(random.randint(3500, 5500))
            payloads.extend(_extract_json_objects(page.content()))
            return payloads
        finally:
            browser.close()


def _enrich_item_variants(
    item: dict[str, Any],
    cookie_file: str | None,
    usd_clp_rate: float,
    price_includes_chile_vat: bool,
) -> tuple[dict[str, Any], str | None]:
    if not item.get("has_variants") or not item.get("url"):
        return item, None
    try:
        payloads = _fetch_detail_payloads(str(item["url"]), cookie_file=cookie_file)
        variants = _extract_variant_details_from_payloads(
            payloads,
            shipping=_clean_number(item.get("shipping")),
            fallback_currency=str(item.get("display_currency") or ""),
            usd_clp_rate=usd_clp_rate,
            price_includes_chile_vat=price_includes_chile_vat,
            is_choice=bool(item.get("is_choice")),
        )
        if not variants:
            return item, "detalle sin matriz de precios por variante"
        item["variants"] = variants
        item["variant_count"] = len(variants)
        item["variant_price_min"] = min(_clean_number(variant.get("price_original")) for variant in variants)
        item["variant_price_max"] = max(_clean_number(variant.get("price_original")) for variant in variants)
        item["variant_price_range_raw"] = [item["variant_price_min"], item["variant_price_max"]]
        item["max_price_clp"] = max(_clean_number(variant.get("price_final_clp")) for variant in variants)
        item["variant_source"] = "detail"
        return item, None
    except Exception as exc:
        return item, str(exc)


def _is_challenge_page(html: str) -> bool:
    lowered = html.lower()
    return (
        "_____tmd_____" in lowered
        or "/punish" in lowered
        or "x5secdata" in lowered
        or "captcha" in lowered and "productid" not in lowered
    )


def collect_results(
    query: str,
    limit: int = 40,
    scan_scope: str = "complete",
    max_pages: int = 3,
    **kwargs,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Realiza busquedas en AliExpress simulando navegacion a Chile.
    Calcula los precios con impuestos incluidos segun las reglas aduaneras chilenas.
    Retorna la lista de productos normalizada y metadatos.
    """
    started = time.perf_counter()
    cleaned_query = (query or "").strip()
    category_id = str(kwargs.get("category_id") or "").strip()
    category = _category_by_id(category_id)
    category_seed = _category_seed(category_id)
    effective_query = cleaned_query
    if category_seed:
        effective_query = f"{cleaned_query} {category_seed}".strip() if cleaned_query else category_seed
    if not effective_query:
        return [], {"total": 0, "pages_fetched": 0, "fetched_raw": 0, "error": "empty_query"}

    target = max(1, min(int(limit or 40), 10_000))
    pages = max(1, int(max_pages or 1))
    if scan_scope != "complete":
        pages = min(pages, 1)

    usd_clp_rate = float(kwargs.get("usd_clp_rate") or DEFAULT_USD_CLP_RATE)
    price_includes_chile_vat = bool(kwargs.get("price_includes_chile_vat", True))
    cookie_file = kwargs.get("cookie_file") or os.getenv("ALIEXPRESS_COOKIE_FILE")
    enrich_variant_details = bool(kwargs.get("enrich_variant_details", False))
    variant_detail_limit = max(0, int(kwargs.get("variant_detail_limit") or 6))
    variant_detail_workers = max(1, min(int(kwargs.get("variant_detail_workers") or 1), 2))
    raw_products: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings_list: list[str] = []
    pages_fetched = 0

    def fetch_page_products(page_num: int) -> tuple[int, list[dict[str, Any]], str | None]:
        retries = max(0, min(int(kwargs.get("challenge_retries") or 0), 2))
        for attempt in range(retries + 1):
            try:
                html = _fetch_search_html(effective_query, page_num, cookie_file=cookie_file)
                if not _is_challenge_page(html):
                    payloads = _extract_json_objects(html)
                    return page_num, _product_nodes(payloads), None
            except Exception as exc:
                if attempt >= retries:
                    return page_num, [], str(exc)
            if attempt < retries:
                time.sleep(float(kwargs.get("challenge_retry_seconds") or 12))
        return page_num, [], "AliExpress challenge/captcha"

    page_num, page_products, error = fetch_page_products(1)
    if error:
        errors.append(f"page {page_num}: {error}")
    else:
        pages_fetched += 1
        raw_products.extend(page_products)

    remaining_pages = list(range(2, pages + 1)) if not error and len(raw_products) < target else []
    if remaining_pages:
        workers = max(1, min(int(kwargs.get("page_workers") or 1), len(remaining_pages), 3))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(fetch_page_products, page_num) for page_num in remaining_pages]
            for future in as_completed(futures):
                page_num, page_products, error = future.result()
                if error:
                    errors.append(f"page {page_num}: {error}")
                    continue
                pages_fetched += 1
                raw_products.extend(page_products)
                if len(raw_products) >= target:
                    break

    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    for raw in raw_products:
        product_id = str(_first_value(raw, ("productId", "product_id", "itemId", "id")) or "")
        if product_id and product_id in seen:
            continue
        if product_id:
            seen.add(product_id)
        normalized = _normalize_product(raw, len(items) + 1, usd_clp_rate, price_includes_chile_vat)
        if not normalized.get("title") or normalized.get("price", 0) <= 0:
            continue
        items.append(normalized)
        if len(items) >= target:
            break

    if enrich_variant_details and variant_detail_limit > 0:
        variant_indexes = [
            index
            for index, item in enumerate(items)
            if item.get("has_variants") and not item.get("variants") and item.get("url")
        ][:variant_detail_limit]
        if variant_indexes:
            with ThreadPoolExecutor(max_workers=min(variant_detail_workers, len(variant_indexes))) as executor:
                future_to_index = {
                    executor.submit(
                        _enrich_item_variants,
                        items[index],
                        cookie_file,
                        usd_clp_rate,
                        price_includes_chile_vat,
                    ): index
                    for index in variant_indexes
                }
                for future in as_completed(future_to_index):
                    index = future_to_index[future]
                    enriched, warning = future.result()
                    items[index] = enriched
                    if warning:
                        warnings_list.append(f"{items[index].get('id')}: {warning}")

    meta = {
        "total": len(items),
        "total_matches": len(items),
        "pages_fetched": pages_fetched,
        "pages_requested": pages,
        "fetched_raw": len(raw_products),
        "query_mode": "playwright",
        "search_url": SEARCH_URL.format(query=urllib.parse.quote(re.sub(r"\s+", "-", effective_query))),
        "category_id": category_id,
        "category": category.get("label") if category else "",
        "category_seed": category_seed,
        "effective_query": effective_query,
        "usd_clp_rate": usd_clp_rate,
        "price_includes_chile_vat": price_includes_chile_vat,
        "enrich_variant_details": enrich_variant_details,
        "variant_detail_limit": variant_detail_limit,
        "variant_details_enriched": sum(1 for item in items if item.get("variant_source") == "detail"),
        "elapsed_seconds": round(time.perf_counter() - started, 2),
    }
    if warnings_list:
        meta["variant_warnings"] = warnings_list[:20]
    if errors:
        meta["errors"] = errors
        error_text = " ".join(errors).lower()
        if not items and ("challenge" in error_text or "anti-bloqueo" in error_text or "captcha" in error_text):
            meta["warning"] = (
                "AliExpress activo una pausa anti-bloqueo temporal. "
                "Espera antes de volver a buscar o configura ALIEXPRESS_PROXY_SERVER."
            )
        else:
            meta["warning"] = "AliExpress no entrego todos los datos solicitados."
    return items, meta


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
    **kwargs,
) -> list[dict[str, Any]]:
    """Aplica filtros locales (precio, palabras incluidas/excluidas)."""
    del kwargs
    filtered: list[dict[str, Any]] = []
    required_word = (word or "").strip().lower()
    include = [str(w).strip().lower() for w in include_words or [] if str(w).strip()]
    exclude = [str(w).strip().lower() for w in exclude_words or [] if str(w).strip()]

    for item in items:
        price = _clean_number(item.get("price"))
        if min_price > 0 and price < min_price:
            continue
        if max_price > 0 and price > max_price:
            continue
        text = _searchable_text(item)
        if required_word and required_word not in text:
            continue
        if include and not all(word in text for word in include):
            continue
        if exclude and any(word in text for word in exclude):
            continue
        filtered.append(item)

    for index, item in enumerate(filtered, start=1):
        item["position"] = index
    return filtered

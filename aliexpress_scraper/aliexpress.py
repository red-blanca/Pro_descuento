from __future__ import annotations

import json
import os
import random
import re
import time
import urllib.parse
import warnings
from typing import Any


SCRAPER_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRAPER_DIR)
BASE_URL = os.getenv("ALIEXPRESS_BASE_URL", "https://es.aliexpress.com")
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
        "Chrome/126.0.0.0 Safari/537.36"
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
    for marker in ("window.runParams", "window.__AER_DATA__", "window._dida_config_"):
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


def _price_from_node(node: dict[str, Any]) -> tuple[float, str]:
    price_info = node.get("priceInfo") if isinstance(node.get("priceInfo"), dict) else {}
    prices = node.get("prices") if isinstance(node.get("prices"), dict) else {}
    sale_price = prices.get("salePrice") if isinstance(prices.get("salePrice"), dict) else {}
    original_price = prices.get("originalPrice") if isinstance(prices.get("originalPrice"), dict) else {}
    for price_dict in (sale_price, original_price):
        parsed = _clean_number(_first_value(price_dict, ("minPrice", "cent", "value", "amount")))
        currency = str(_first_value(price_dict, ("currencyCode", "currency", "symbol")) or "").upper()
        if parsed > 0:
            return parsed, currency
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
        if isinstance(candidate, dict):
            amount = _first_value(candidate, ("value", "amount", "minPrice", "salePrice"))
            currency = str(_first_value(candidate, ("currency", "currencyCode", "symbol")) or "").upper()
            parsed = _clean_number(amount)
            if parsed > 0:
                return parsed, currency
        parsed = _clean_number(candidate)
        if parsed > 0:
            text = str(candidate or "").upper()
            currency = "USD" if "US" in text or "USD" in text else ("CLP" if "$" in text or "CLP" in text else "")
            return parsed, currency
    return 0.0, ""


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

    if display_total_usd <= USD_CIF_THRESHOLD:
        if price_includes_chile_vat:
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
        net_cif_usd = display_total_usd
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
    price, currency = _price_from_node(node)
    shipping = _shipping_from_node(node, currency)
    display_total = price + shipping
    cost = _calculate_chile_cost(display_total, currency, usd_clp_rate, price_includes_chile_vat)
    url = _absolute_url(_first_value(node, ("productDetailUrl", "productUrl", "url", "link")))
    if not url and product_id:
        url = f"{BASE_URL}/item/{product_id}.html"

    image_value = _first_value(node, ("imageUrl", "productImage", "imgUrl", "image"))
    if isinstance(image_value, dict):
        image_value = _first_value(image_value, ("imgUrl", "url", "imageUrl"))
    image = _absolute_url(image_value)
    brand = _first_value(node, ("brand", "brandName"))
    category = _first_value(node, ("category", "categoryName"))

    return {
        "id": f"aliexpress#{product_id}",
        "title": title,
        "name": title,
        "price": float(cost["final_price_clp"]),
        "formatted_price": _format_clp(float(cost["final_price_clp"])),
        "url": url,
        "link": url,
        "image": image,
        "store": "AliExpress",
        "brand": str(brand).strip() if brand else None,
        "category": str(category).strip() if category else None,
        "discount_percent": _discount_from_node(node),
        "original_price_usd": float(cost["original_price_usd"]),
        "tax_applied_usd": float(cost["tax_applied_usd"]),
        "final_price_usd": float(cost["final_price_usd"]),
        "display_price_raw": price,
        "display_currency": currency or "CLP",
        "shipping_raw": shipping,
        "duty_applied_usd": float(cost["duty_applied_usd"]),
        "iva_applied_usd": float(cost["iva_applied_usd"]),
        "handling_fee_usd": float(cost["handling_fee_usd"]),
        "over_usd_500": bool(cost["over_usd_500"]),
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

    encoded_query = urllib.parse.quote(re.sub(r"\s+", "-", query.strip()))
    url = SEARCH_URL.format(query=encoded_query)
    if page_num > 1:
        url = f"{url}?page={page_num}"

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
            page.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'languages', { get: () => ['es-CL', 'es', 'en'] });
                Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
                """
            )
            page.goto(url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
            page.wait_for_timeout(random.randint(1600, 2600))
            return page.content()
        finally:
            browser.close()


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
    if not cleaned_query:
        return [], {"total": 0, "pages_fetched": 0, "fetched_raw": 0, "error": "empty_query"}

    target = max(1, min(int(limit or 40), 10_000))
    pages = max(1, int(max_pages or 1))
    if scan_scope != "complete":
        pages = min(pages, 1)

    usd_clp_rate = float(kwargs.get("usd_clp_rate") or DEFAULT_USD_CLP_RATE)
    price_includes_chile_vat = bool(kwargs.get("price_includes_chile_vat", True))
    cookie_file = kwargs.get("cookie_file") or os.getenv("ALIEXPRESS_COOKIE_FILE")
    raw_products: list[dict[str, Any]] = []
    errors: list[str] = []
    pages_fetched = 0

    for page_num in range(1, pages + 1):
        try:
            html = _fetch_search_html(cleaned_query, page_num, cookie_file=cookie_file)
            if _is_challenge_page(html):
                errors.append(f"page {page_num}: AliExpress challenge/captcha")
                if page_num == 1:
                    break
                continue
            payloads = _extract_json_objects(html)
            page_products = _product_nodes(payloads)
            pages_fetched += 1
            raw_products.extend(page_products)
        except Exception as exc:
            errors.append(f"page {page_num}: {exc}")
            if page_num == 1:
                break
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

    meta = {
        "total": len(items),
        "total_matches": len(items),
        "pages_fetched": pages_fetched,
        "pages_requested": pages,
        "fetched_raw": len(raw_products),
        "query_mode": "playwright",
        "search_url": SEARCH_URL.format(query=urllib.parse.quote(re.sub(r"\s+", "-", cleaned_query))),
        "usd_clp_rate": usd_clp_rate,
        "price_includes_chile_vat": price_includes_chile_vat,
        "elapsed_seconds": round(time.perf_counter() - started, 2),
    }
    if errors:
        meta["errors"] = errors
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

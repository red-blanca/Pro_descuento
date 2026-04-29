"""
Pulga.cl Scraper — CLI + Library
Uses the public REST API at admin.segundamano.ai to fetch product listings.

Usage:
    python pulga.py notebook --limit 20 --json
    python pulga.py iphone --category tecnologia --all-results --export-xlsx
    python pulga.py zapatillas --min-price 10000 --max-price 50000 --condition used
"""
from __future__ import annotations

import argparse
import json
import re
import socket
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from zipfile import ZIP_DEFLATED, ZipFile

API_BASE = "https://admin.segundamano.ai/api/get-item"
PRODUCT_URL_BASE = "https://pulga.cl/product"
PER_PAGE = 20
REQUEST_DELAY = 0.3  # seconds between API requests (sequential mode)
CONCURRENT_WORKERS = 4  # keep Pulga's API from timing out under bursty parallel fetches
REQUEST_RETRIES = 4

CATEGORY_SLUGS: dict[str, str] = {
    "tecnologia": "technology-electronics",
    "moda": "fashion",
    "bebes": "baby-kids",
    "entretenimiento": "entertainment",
    "coleccionismo": "collectibles",
    "deporte": "sports",
    "bicicletas": "bicycles",
    "hogar": "home-garden",
    "electrodomesticos": "appliances",
}

CONDITION_MAP: dict[str, str] = {
    "nuevo": "new",
    "usado": "used",
    "new": "new",
    "used": "used",
    "any": "any",
    "cualquiera": "any",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _is_retryable_error(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, socket.timeout, ConnectionError)):
        return True
    if isinstance(exc, HTTPError):
        return exc.code in {408, 429, 500, 502, 503, 504}
    if isinstance(exc, URLError):
        return True
    return False


def _sleep_before_retry(attempt: int) -> None:
    time.sleep(min(0.7 * (2 ** attempt), 5.0))


def _progress(prefix: str, current: int, total: int | None = None) -> None:
    if total and total > 0:
        pct = min(100, int((current / total) * 100))
        bar_w = 24
        filled = int((pct / 100) * bar_w)
        bar = "#" * filled + "-" * (bar_w - filled)
        msg = f"\r{prefix} [{bar}] {pct:3d}% ({current}/{total})"
    else:
        msg = f"\r{prefix} {current}"
    print(msg, end="", file=sys.stderr, flush=True)


def _progress_done() -> None:
    print(file=sys.stderr, flush=True)


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    no_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return no_accents.lower().strip()


def text_has_term(text: str, term: str) -> bool:
    term = term.strip()
    if not term:
        return False
    return term in text


def parse_price_value(price: Any) -> int | None:
    if price is None:
        return None
    if isinstance(price, (int, float)):
        return int(price)
    digits = "".join(ch for ch in str(price) if ch.isdigit())
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def resolve_category_slug(category: str) -> str | None:
    if not category or not category.strip():
        return None
    key = category.strip().lower()
    if key in CATEGORY_SLUGS:
        return CATEGORY_SLUGS[key]
    # Maybe they passed the slug directly
    if key in CATEGORY_SLUGS.values():
        return key
    return None


def fetch_api_page(
    page: int = 1,
    search: str = "",
    category_slug: str | None = None,
    timeout: int = 35,
) -> dict[str, Any]:
    """Fetch a single page from the Pulga API."""
    params: dict[str, str] = {"page": str(page)}
    if search.strip():
        params["search"] = search.strip()
    if category_slug:
        params["category_slug"] = category_slug

    url = f"{API_BASE}?{urlencode(params)}"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Origin": "https://pulga.cl",
        "Referer": "https://pulga.cl/",
    }
    req = Request(url, headers=headers)
    last_error: BaseException | None = None
    for attempt in range(REQUEST_RETRIES):
        try:
            with urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", errors="ignore"))
        except HTTPError as exc:
            last_error = exc
            if exc.code == 404 or not _is_retryable_error(exc):
                raise
        except (TimeoutError, socket.timeout, ConnectionError, URLError) as exc:
            last_error = exc
        if attempt < REQUEST_RETRIES - 1:
            _sleep_before_retry(attempt)
    raise RuntimeError(f"No se pudo leer Pulga.cl tras {REQUEST_RETRIES} intentos: {last_error}") from last_error


def normalize_item(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw API item into a clean dict."""
    slug = str(raw.get("slug") or "").strip()
    link = f"{PRODUCT_URL_BASE}/{slug}" if slug else ""

    # Extract category name
    cat = raw.get("category") or {}
    cat_name = ""
    if isinstance(cat, dict):
        cat_name = str(cat.get("name") or "").strip()

    # Extract seller name
    user = raw.get("user") or {}
    seller = ""
    if isinstance(user, dict):
        seller = str(user.get("name") or "").strip()

    # Gallery images
    gallery = raw.get("gallery_images") or []
    images: list[str] = []
    main_image = str(raw.get("image") or "").strip()
    if main_image:
        images.append(main_image)
    for gi in gallery:
        if isinstance(gi, dict):
            img_url = str(gi.get("image") or "").strip()
            if img_url and img_url not in images:
                images.append(img_url)

    price = parse_price_value(raw.get("price"))
    price_with_fee = parse_price_value(raw.get("price_with_fee"))

    return {
        "id": raw.get("id"),
        "title": str(raw.get("name") or "").strip(),
        "slug": slug,
        "description": str(raw.get("description") or "").strip(),
        "condition": str(raw.get("item_condition") or "").strip().lower(),
        "price": price,
        "price_with_fee": price_with_fee,
        "price_display": f"$ {price_with_fee:,.0f}".replace(",", ".") if price_with_fee else "",
        "link": link,
        "image": main_image,
        "images": images,
        "city": str(raw.get("city") or "").strip(),
        "address": str(raw.get("address") or "").strip(),
        "latitude": raw.get("latitude"),
        "longitude": raw.get("longitude"),
        "category": cat_name,
        "seller": seller,
        "created_at": str(raw.get("created_at") or "").strip(),
        "clicks": raw.get("clicks") or 0,
        "total_likes": raw.get("total_likes") or 0,
    }


def quick_count(
    query: str = "",
    category: str | None = None,
    timeout: int = 35,
) -> tuple[int, int]:
    """
    Get the total count from a single API request (no pagination).
    Returns (total_items, total_pages).
    """
    category_slug = resolve_category_slug(category) if category else None
    response = fetch_api_page(page=1, search=query, category_slug=category_slug, timeout=timeout)
    data = response.get("data", {})
    if not isinstance(data, dict):
        return 0, 0
    return int(data.get("total") or 0), int(data.get("last_page") or 0)


def _fetch_and_normalize(page: int, search: str, category_slug: str | None, timeout: int) -> tuple[int, list[dict[str, Any]]]:
    """Fetch a single page and normalize items. Returns (page_number, items)."""
    try:
        response = fetch_api_page(page=page, search=search, category_slug=category_slug, timeout=timeout)
    except HTTPError as exc:
        if exc.code == 404:
            return page, []
        raise
    data = response.get("data", {})
    if not isinstance(data, dict):
        return page, []
    raw_items = data.get("data") or []
    return page, [normalize_item(r) for r in raw_items]


def collect_results(
    query: str = "",
    category: str | None = None,
    limit: int = 20,
    fetch_all: bool = False,
    max_pages: int = 0,
    timeout: int = 35,
    delay: float = REQUEST_DELAY,
    quiet: bool = False,
    workers: int = CONCURRENT_WORKERS,
) -> tuple[list[dict[str, Any]], int]:
    """
    Collect product listings from the Pulga API using concurrent fetching.
    Returns (items, total_available).
    """
    category_slug = resolve_category_slug(category) if category else None

    # ── Step 1: fetch page 1 to discover total & last_page ──
    if not quiet:
        _progress("Pagina 1 (descubrimiento)", 1)

    try:
        first_response = fetch_api_page(page=1, search=query, category_slug=category_slug, timeout=timeout)
    except HTTPError as exc:
        if exc.code == 404:
            if not quiet:
                _progress_done()
            return [], 0
        raise

    first_data = first_response.get("data", {})
    if not isinstance(first_data, dict):
        if not quiet:
            _progress_done()
        return [], 0

    total_available = int(first_data.get("total") or 0)
    last_page = int(first_data.get("last_page") or 1)
    first_items_raw = first_data.get("data") or []
    collected = [normalize_item(r) for r in first_items_raw]

    # Early return if only one page or limit already reached
    if not fetch_all and len(collected) >= limit:
        if not quiet:
            _progress_done()
        return collected[:limit], total_available

    if last_page <= 1:
        if not quiet:
            _progress_done()
        return (collected if fetch_all else collected[:limit]), total_available

    # ── Step 2: determine which pages to fetch ──
    target_last = last_page
    if max_pages > 0:
        target_last = min(last_page, max_pages)
    if not fetch_all and max_pages <= 0:
        # Compute how many pages we need for the requested limit
        needed_pages = min(last_page, -(-limit // PER_PAGE))  # ceiling division
        target_last = max(1, needed_pages)

    remaining_pages = list(range(2, target_last + 1))
    if not remaining_pages:
        if not quiet:
            _progress_done()
        return (collected if fetch_all else collected[:limit]), total_available

    # ── Step 3: fetch remaining pages concurrently ──
    effective_workers = min(workers, len(remaining_pages))
    pages_done = 1  # we already have page 1
    total_to_fetch = len(remaining_pages) + 1

    page_results: dict[int, list[dict[str, Any]]] = {}

    if not quiet:
        _progress("Recolectando", pages_done, total_to_fetch)

    with ThreadPoolExecutor(max_workers=effective_workers) as pool:
        futures = {
            pool.submit(_fetch_and_normalize, pg, query, category_slug, timeout): pg
            for pg in remaining_pages
        }
        for future in as_completed(futures):
            page_num, items = future.result()
            page_results[page_num] = items
            pages_done += 1
            if not quiet:
                _progress("Recolectando", pages_done, total_to_fetch)

    # ── Step 4: merge results in page order ──
    for pg in sorted(page_results.keys()):
        collected.extend(page_results[pg])

    if not quiet:
        _progress_done()

    # Assign positions
    for idx, item in enumerate(collected, start=1):
        item["position"] = idx

    return (collected if fetch_all else collected[:limit]), total_available


def apply_filters(
    items: list[dict[str, Any]],
    min_price: int = 0,
    max_price: int = 0,
    condition_filter: str = "any",
    word: str = "",
    include_words: list[str] | None = None,
    exclude_words: list[str] | None = None,
    city_filter: str = "",
) -> list[dict[str, Any]]:
    """Apply client-side filters to collected items."""
    include_words = include_words or []
    exclude_words = exclude_words or []

    word_lc = normalize_text(word) if word.strip() else ""
    include_lc = [normalize_text(w) for w in include_words if str(w).strip()]
    exclude_lc = [normalize_text(w) for w in exclude_words if str(w).strip()]
    city_lc = normalize_text(city_filter) if city_filter.strip() else ""
    condition_lc = CONDITION_MAP.get(condition_filter.strip().lower(), "any")

    out: list[dict[str, Any]] = []
    for item in items:
        title_lc = normalize_text(item.get("title", ""))
        price_val = item.get("price_with_fee") or item.get("price")

        # Price filters
        if min_price > 0 and (price_val is None or price_val < min_price):
            continue
        if max_price > 0 and (price_val is None or price_val > max_price):
            continue

        # Condition filter
        if condition_lc != "any":
            item_cond = str(item.get("condition") or "").strip().lower()
            if item_cond != condition_lc:
                continue

        # Word filters
        if word_lc and not text_has_term(title_lc, word_lc):
            continue
        if include_lc and not all(text_has_term(title_lc, w) for w in include_lc):
            continue
        if exclude_lc and any(text_has_term(title_lc, w) for w in exclude_lc):
            continue

        # City filter
        if city_lc:
            item_city = normalize_text(item.get("city", ""))
            if city_lc not in item_city:
                continue

        out.append(item)

    return out


def sort_items_by_price(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key_fn(item: dict[str, Any]) -> tuple[int, int]:
        price = item.get("price_with_fee") or item.get("price")
        if price is None:
            return (1, 10**18)
        return (0, int(price))

    sorted_items = sorted(items, key=key_fn)
    for idx, item in enumerate(sorted_items, start=1):
        item["position"] = idx
    return sorted_items


# ── Excel export (zero-dependency XLSX) ──────────────────────────────────


def xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def build_xlsx_bytes(items: list[dict[str, Any]]) -> bytes:
    headers = ["Posicion", "Titulo", "Precio", "Precio c/comision", "Condicion", "Ciudad", "Vendedor", "Link"]
    condition_map = {"new": "Nuevo", "used": "Usado"}
    rows: list[list[str | int]] = [headers]
    for idx, item in enumerate(items, start=1):
        cond = condition_map.get(str(item.get("condition") or "").lower(), "N/D")
        rows.append([
            idx,
            str(item.get("title") or ""),
            f"$ {item.get('price', 0):,.0f}".replace(",", ".") if item.get("price") else "",
            item.get("price_display", ""),
            cond,
            str(item.get("city") or ""),
            str(item.get("seller") or ""),
            str(item.get("link") or ""),
        ])

    sheet_rows: list[str] = []
    for r_idx, row in enumerate(rows, start=1):
        cells: list[str] = []
        for c_idx, value in enumerate(row, start=1):
            col = ""
            n = c_idx
            while n:
                n, rem = divmod(n - 1, 26)
                col = chr(65 + rem) + col
            ref = f"{col}{r_idx}"
            if isinstance(value, int):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{xml_escape(str(value))}</t></is></c>')
        sheet_rows.append(f'<row r="{r_idx}">{"".join(cells)}</row>')

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(sheet_rows)}</sheetData>"
        "</worksheet>"
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Resultados" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )

    buf = BytesIO()
    with ZipFile(buf, mode="w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return buf.getvalue()


def export_xlsx(items: list[dict[str, Any]], query: str, output_path: str | None) -> Path:
    if output_path and output_path != "__AUTO__":
        out = Path(output_path)
    else:
        safe_query = re.sub(r"[^a-zA-Z0-9_-]+", "_", query)[:40].strip("_") or "busqueda"
        out = Path("exports") / f"pulga_{safe_query}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.xlsx"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(build_xlsx_bytes(items))
    return out


# ── CLI ──────────────────────────────────────────────────────────────────


def run(
    query: str,
    limit: int,
    as_json: bool,
    category: str | None,
    condition_filter: str,
    fetch_all: bool,
    max_pages: int,
    min_price: int,
    max_price: int,
    word_filter: str,
    include_words: list[str],
    exclude_words: list[str],
    sort_price: bool,
    export_xlsx_path: str | None,
    city_filter: str,
) -> int:
    items, total = collect_results(
        query=query,
        category=category,
        limit=limit,
        fetch_all=fetch_all,
        max_pages=max_pages,
    )

    items = apply_filters(
        items,
        min_price=min_price,
        max_price=max_price,
        condition_filter=condition_filter,
        word=word_filter,
        include_words=include_words,
        exclude_words=exclude_words,
        city_filter=city_filter,
    )

    if sort_price:
        items = sort_items_by_price(items)
    else:
        for idx, item in enumerate(items, start=1):
            item["position"] = idx

    if not items:
        if export_xlsx_path is not None:
            out = export_xlsx(items, query=query, output_path=export_xlsx_path)
            print(f"Excel generado (vacio): {out}")
            return 0
        if as_json:
            print("[]")
            return 0
        print("No se encontraron resultados con esos filtros.")
        return 0

    if export_xlsx_path is not None:
        out = export_xlsx(items, query=query, output_path=export_xlsx_path)
        print(f"Excel generado: {out} ({len(items)} productos)")
        return 0

    if as_json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return 0

    print(f"Resultados para: {query!r} (mostrando {len(items)} de {total} disponibles)\n")
    condition_map = {"new": "Nuevo", "used": "Usado"}
    for item in items:
        cond = condition_map.get(item.get("condition", ""), "")
        print(f"{item['position']}. {item['title']}")
        print(f"   Precio: {item.get('price_display') or 'N/D'}")
        if cond:
            print(f"   Condicion: {cond}")
        if item.get("city"):
            print(f"   Ciudad: {item['city']}")
        print(f"   Link: {item['link']}")

    return 0


def main() -> int:
    started_at = time.perf_counter()
    exit_code = 0

    parser = argparse.ArgumentParser(
        description="Scraper de Pulga.cl — Marketplace de segunda mano en Chile."
    )
    parser.add_argument(
        "query",
        nargs="*",
        default=[],
        help="Termino de busqueda (ej: notebook, iphone)",
    )
    parser.add_argument(
        "--category",
        choices=sorted(CATEGORY_SLUGS.keys()),
        default=None,
        help="Categoria (ej: tecnologia, moda, bebes)",
    )
    parser.add_argument(
        "--limit", type=int, default=20, help="Cantidad maxima de resultados"
    )
    parser.add_argument(
        "--json", action="store_true", help="Imprime los resultados en JSON"
    )
    parser.add_argument(
        "--condition",
        choices=["any", "new", "used"],
        default="any",
        help="Filtra por condicion del producto",
    )
    parser.add_argument(
        "--estado",
        choices=["cualquiera", "nuevo", "usado"],
        default=None,
        help="Alias en espanol de --condition",
    )
    parser.add_argument(
        "--all-results",
        action="store_true",
        help="Recorre todas las paginas disponibles",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=0,
        help="Maximo de paginas a recorrer (0 = sin limite)",
    )
    parser.add_argument(
        "--min-price", type=int, default=0, help="Precio minimo"
    )
    parser.add_argument(
        "--max-price", type=int, default=0, help="Precio maximo"
    )
    parser.add_argument(
        "--word", default="", help="Filtra resultados por palabra en el titulo"
    )
    parser.add_argument(
        "--include-word",
        action="append",
        default=[],
        help="Palabra obligatoria en titulo. Repetir para varias.",
    )
    parser.add_argument(
        "--exclude-word",
        action="append",
        default=[],
        help="Palabra a descartar en titulo. Repetir para varias.",
    )
    parser.add_argument(
        "--sort-price",
        action="store_true",
        help="Ordena resultados por precio ascendente",
    )
    parser.add_argument(
        "--export-xlsx",
        nargs="?",
        const="__AUTO__",
        default=None,
        help="Exporta a Excel. Opcional: ruta de salida",
    )
    parser.add_argument(
        "--city",
        default="",
        help="Filtrar por ciudad (ej: Santiago, Curico)",
    )

    args = parser.parse_args()
    query = " ".join(args.query).strip()

    condition = args.condition
    if args.estado:
        condition = CONDITION_MAP.get(args.estado, "any")

    if not query and not args.category:
        print("Debes indicar un termino de busqueda o una categoria.")
        return 2

    try:
        exit_code = run(
            query,
            args.limit,
            args.json,
            args.category,
            condition,
            args.all_results,
            args.max_pages,
            max(0, args.min_price),
            max(0, args.max_price),
            args.word,
            args.include_word,
            args.exclude_word,
            args.sort_price,
            args.export_xlsx,
            args.city,
        )
        return exit_code
    except Exception as exc:
        print(f"Error al obtener datos de Pulga.cl: {exc}", file=sys.stderr)
        return 1
    finally:
        elapsed = time.perf_counter() - started_at
        print(f"Tiempo total: {elapsed:.2f}s")


if __name__ == "__main__":
    raise SystemExit(main())

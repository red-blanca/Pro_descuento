from __future__ import annotations

import json
import re
import ssl
import time
import urllib.parse
import urllib.request
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from dataclasses import dataclass, field
from typing import Any

BASE_URL = "https://descuentosrata.com"
OFFERS_URL = f"{BASE_URL}/oferta"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

def xml_escape(value: str) -> str:
    return (
        str(value).replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )

def build_xlsx_bytes(items: list[dict[str, Any]]) -> bytes:
    headers = ["Posicion", "Tienda", "Titulo", "Precio", "Descuento", "Link"]
    rows: list[list[str | int]] = [headers]
    for idx, item in enumerate(items, start=1):
        rows.append([
            idx,
            str(item.get("store") or ""),
            str(item.get("title") or ""),
            item.get("price") or 0,
            f"{item.get('discount_percentage')}%" if item.get("discount_percentage") else "",
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
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{xml_escape(value)}</t></is></c>')
        sheet_rows.append(f"<row r=\"{r_idx}\">{''.join(cells)}</row>")

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

@dataclass
class SearchOptions:
    query: str = ""
    min_price: int = 0
    max_price: int = 0
    limit: int = 100

@dataclass
class SearchResult:
    items: list[dict[str, Any]]
    total_matches: int
    search_url: str

def fetch_html(url: str, timeout: int = 20) -> str:
    headers = {"User-Agent": USER_AGENT}
    req = urllib.request.Request(url, headers=headers)
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(req, timeout=timeout, context=context) as response:
        return response.read().decode("utf-8", errors="ignore")

def parse_price(price_str: str) -> int:
    digits = "".join(ch for ch in price_str if ch.isdigit())
    return int(digits) if digits else 0

def extract_offers(html: str) -> list[dict[str, Any]]:
    offers = []
    
    # Cada tarjeta de oferta está dentro de un div con col y contiene un <a> con clase text-decoration-none
    # El patrón busca el bloque de la oferta
    card_pattern = re.compile(r'<a[^>]+href="(/oferta/[^"]+)"[^>]*class="[^"]*text-decoration-none[^"]*"[^>]*>(.*?)</a>', re.DOTALL)
    
    for match in card_pattern.finditer(html):
        link_path = match.group(1)
        content = match.group(2)
        
        link = urllib.parse.urljoin(BASE_URL, link_path)
            
        # Tienda: <h6 class="... line-clamp--1">Tienda</h6>
        store_match = re.search(r'<h6[^>]*>(.*?)</h6>', content, re.IGNORECASE | re.DOTALL)
        store = clean_html(store_match.group(1)) if store_match else "Desconocido"
        
        # Título: <div class="... line-clamp--3 mb-2">Título</div>
        title_match = re.search(r'<div[^>]*class="[^"]*line-clamp--3[^"]*"[^>]*>(.*?)</div>', content, re.IGNORECASE | re.DOTALL)
        title = clean_html(title_match.group(1)) if title_match else ""
        
        # Precio actual: <span class="... rata-font-poppins ...">$24.990</span>
        price_match = re.search(r'<span[^>]*class="[^"]*rata-font-poppins[^"]*"[^>]*>(.*?)</span>', content, re.IGNORECASE | re.DOTALL)
        current_price_str = price_match.group(1) if price_match else ""
        current_price = parse_price(current_price_str)
        
        # Precio anterior: <small aria-label="Precio anterior" ...><small>$89.990</small></small>
        old_price_match = re.search(r'aria-label="Precio anterior"[^>]*>.*?<small[^>]*>(.*?)</small>', content, re.IGNORECASE | re.DOTALL)
        original_price_str = old_price_match.group(1) if old_price_match else ""
        original_price = parse_price(original_price_str)
        
        # Imagen: La página parece usar lazy loading o componentes de Nuxt. 
        # Si no hay img directa, buscaremos el patrón de imagen
        img_match = re.search(r'<img[^>]+src="([^"]+)"', content, re.IGNORECASE)
        image = img_match.group(1) if img_match else ""

        discount = 0
        if original_price > current_price and original_price > 0:
            discount = round(((original_price - current_price) / original_price) * 100)

        if title:
            offers.append({
                "title": title,
                "store": store,
                "price": current_price,
                "formatted_price": f"$ {current_price:,}".replace(",", "."),
                "original_price": original_price,
                "formatted_original_price": f"$ {original_price:,}".replace(",", ".") if original_price else "",
                "discount_percentage": discount,
                "link": link,
                "image": image,
            })
        
    return offers

def clean_html(raw_html: str) -> str:
    # Eliminar tags HTML
    clean = re.sub(r'<[^>]+>', '', raw_html)
    # Decodificar entidades comunes y limpiar espacios
    clean = " ".join(clean.split())
    return clean

def execute_search(opts: SearchOptions) -> SearchResult:
    html = fetch_html(OFFERS_URL)
    all_offers = extract_offers(html)
    
    # Filtrar por query
    filtered = all_offers
    if opts.query:
        query = opts.query.lower()
        filtered = [o for o in filtered if query in o["title"].lower() or query in o["store"].lower()]
        
    # Filtrar por precio
    if opts.min_price > 0:
        filtered = [o for o in filtered if o["price"] >= opts.min_price]
    if opts.max_price > 0:
        filtered = [o for o in filtered if o["price"] <= opts.max_price]
        
    return SearchResult(
        items=filtered[:opts.limit],
        total_matches=len(filtered),
        search_url=OFFERS_URL
    )

if __name__ == "__main__":
    res = execute_search(SearchOptions(limit=5))
    for item in res.items:
        print(f"[{item['store']}] {item['title']} - {item['formatted_price']}")

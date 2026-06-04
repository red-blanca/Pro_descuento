from __future__ import annotations
import sys
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
TUGANGA_PATH = str(ROOT / "tuganga_scraper")
if TUGANGA_PATH not in sys.path:
    sys.path.append(TUGANGA_PATH)

try:
    import tuganga_api
except ImportError:
    sys.path.append(os.getcwd())
    import tuganga_api

def collect_results(
    query: str,
    limit: int = 40,
    scan_scope: str = "fast",
    max_pages: int = 3,
    **kwargs
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Collect results from pcFactory using TuGanga as a proxy.
    """
    opts = tuganga_api.SearchOptions(
        query=query,
        stores=["pcfactory"],
        limit=limit,
        max_pages=max_pages if scan_scope == "complete" else 2,
        scan_scope=scan_scope
    )

    result = tuganga_api.execute_search(opts)

    # Normalize items
    normalized_items = []
    for item in result.items:
        normalized_items.append({
            "id": f"pcfactory#{item.get('id')}",
            "title": item.get("title"),
            "name": item.get("title"),
            "price": item.get("price"),
            "formatted_price": item.get("formatted_price"),
            "url": item.get("url"),
            "link": item.get("url"),
            "image": item.get("image"),
            "store": "pcFactory",
            "brand": item.get("brand"),
            "category": item.get("category"),
            "discount_percent": item.get("discount_percentage"),
        })

    meta = {
        "total": result.total_matches,
        "pages_fetched": result.pages_fetched,
        "fetched_raw": result.fetched_raw,
        "search_url": result.search_url
    }
    return normalized_items, meta

def apply_filters(
    items: list[dict[str, Any]],
    min_price: float = 0,
    max_price: float = 0,
    word: str = "",
    include_words: list[str] | None = None,
    exclude_words: list[str] | None = None,
    **kwargs
) -> list[dict[str, Any]]:
    filtered = []
    for item in items:
        price = item.get("price") or 0
        try:
            price_val = float(price)
        except (TypeError, ValueError):
            price_val = 0

        if min_price > 0 and price_val < min_price:
            continue
        if max_price > 0 and price_val > max_price:
            continue

        title = (item.get("title") or "").lower()

        if word and word.lower() not in title:
            continue

        if include_words:
            if not all(w.lower() in title for w in include_words if w.strip()):
                continue
        if exclude_words:
            if any(w.lower() in title for w in exclude_words if w.strip()):
                continue
        filtered.append(item)
    return filtered

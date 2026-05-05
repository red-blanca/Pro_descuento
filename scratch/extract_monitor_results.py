from __future__ import annotations

import json
import sys
import time
import traceback
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "exports" / "monitor_2026-05-03"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "facebook_marketplace"))
sys.path.insert(0, str(ROOT / "pulga"))
sys.path.insert(0, str(ROOT / "knasta_scraper"))
sys.path.insert(0, str(ROOT / "solotodo_scraper"))
sys.path.insert(0, str(ROOT / "travel_scraper"))
sys.path.insert(0, str(ROOT / "tuganga_scraper"))
sys.path.insert(0, str(ROOT / "descuentosrata_scraper"))


def write_json(name: str, payload: Any) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def dataclass_to_dict(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    return value


def run_source(name: str, fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    started = time.perf_counter()
    print(f"[{name}] ejecutando...")
    try:
        payload = fn()
        payload["ok"] = True
    except Exception as exc:
        payload = {
            "ok": False,
            "source": name,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "items": [],
            "count": 0,
        }
    payload["elapsed_seconds"] = round(time.perf_counter() - started, 2)
    path = write_json(name, payload)
    payload["output_file"] = str(path)
    print(f"[{name}] {len(payload.get('items') or [])} items -> {path}")
    return payload


def mercadolibre_used() -> dict[str, Any]:
    import mercadolibre as ml

    cookie_file = ROOT / "cookies.txt"
    if cookie_file.exists():
        ml.configure_cookie_header(None, str(cookie_file))
    items = ml.collect_results(
        query="monitor",
        country="cl",
        limit=10000,
        fetch_all=True,
        max_pages=20,
        exclude_international=True,
        min_price=0,
        max_price=0,
        min_discount=0,
        sort_price=False,
        condition_filter="used",
        search_url=None,
        timeout=25,
        quiet=False,
    )
    return {
        "source": "mercadolibre",
        "query": "monitor",
        "condition": "used",
        "category_note": "MercadoLibre filtrado por condición usada; búsqueda en CL.",
        "count": len(items),
        "items": items,
    }


def facebook_curico_talca() -> dict[str, Any]:
    import facebook_api as fb

    cookies = fb.load_cookie_profiles()
    opts = fb.SearchOptions(
        query="monitor",
        marketplace_path="curico",
        limit=500,
        max_pages=8,
        location_query="Curico, Maule, Chile",
        latitude=-34.98749193781055,
        longitude=-71.24675716218236,
        radius_km=35,
        include_talca=True,
        country_code="CL",
    )
    result = fb.execute_search(opts, cookies)
    return {
        "source": "facebook_marketplace",
        "query": "monitor",
        "locations": ["Curico, Maule, Chile", "Talca, Maule, Chile"],
        "count": len(result.items),
        "total_matches": result.total_matches,
        "captured_raw": result.captured_raw,
        "filter_breakdown": result.filter_breakdown,
        "items": result.items,
    }


def pulga_tecnologia() -> dict[str, Any]:
    import pulga

    items, total_available = pulga.collect_results(
        query="monitor",
        category="tecnologia",
        limit=10000,
        fetch_all=True,
        timeout=25,
        quiet=False,
    )
    items = pulga.apply_filters(items, condition_filter="any")
    return {
        "source": "pulga",
        "query": "monitor",
        "category": "tecnologia",
        "category_slug": "technology-electronics",
        "total_available": total_available,
        "count": len(items),
        "items": items,
    }


def knasta_tecnologia() -> dict[str, Any]:
    import knasta_api as knasta

    opts = knasta.SearchOptions(
        query="monitor",
        category="20106",
        limit=10000,
        max_pages=200,
        scan_scope="complete",
    )
    result = knasta.execute_search(opts)
    return {
        "source": "knasta",
        "query": "monitor",
        "category": {"id": "20106", "name": "Tecnología"},
        **dataclass_to_dict(result),
        "count": len(result.items),
    }


def solotodo_monitores() -> dict[str, Any]:
    import solotodo

    items, meta = solotodo.collect_browse_results(
        query="monitor",
        category_id=4,
        country_id=1,
        ordering="offer_price_usd",
        limit=10000,
        fetch_all=True,
    )
    items = solotodo.apply_filters(items)
    return {
        "source": "solotodo",
        "query": "monitor",
        "category": {"id": 4, "name": "Monitores", "slug": "monitores"},
        "meta": meta,
        "count": len(items),
        "items": items,
    }


def travel_monitores() -> dict[str, Any]:
    import travel

    items, meta = travel.collect_results(
        query="monitor",
        category_id="TiendaMonitores",
        ordering="relevance",
        limit=10000,
        fetch_all=True,
    )
    return {
        "source": "travel",
        "query": "monitor",
        "category": {
            "id": "TiendaMonitores",
            "path": "Tecnología / Computación / Monitores",
        },
        "meta": meta,
        "count": len(items),
        "items": items,
    }


def tuganga_computacion() -> dict[str, Any]:
    import tuganga_api as tg

    categories = [
        "computacion-automated",
        "computacion-rscore",
        "computacion-gamer-rscore",
        "computacion-gamer-automated",
    ]
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    runs = []
    for category in categories:
        opts = tg.SearchOptions(
            query="monitor",
            mode="search",
            category=category,
            limit=10000,
            max_pages=200,
            scan_scope="complete",
        )
        result = tg.execute_search(opts)
        runs.append(dataclass_to_dict(result))
        for item in result.items:
            key = str(item.get("url") or item.get("id") or json.dumps(item, sort_keys=True))
            if key in seen:
                continue
            seen.add(key)
            items.append(item)
    return {
        "source": "tuganga",
        "query": "monitor",
        "categories": categories,
        "runs": runs,
        "count": len(items),
        "items": items,
    }


def descuentosrata() -> dict[str, Any]:
    import descuentosrata_api as dr

    result = dr.execute_search(dr.SearchOptions(query="monitor", limit=10000))
    return {
        "source": "descuentosrata",
        "query": "monitor",
        **dataclass_to_dict(result),
        "count": len(result.items),
    }


def main() -> int:
    sources: list[tuple[str, Callable[[], dict[str, Any]]]] = [
        ("mercadolibre_used", mercadolibre_used),
        ("facebook_curico_talca", facebook_curico_talca),
        ("pulga_tecnologia", pulga_tecnologia),
        ("knasta_tecnologia", knasta_tecnologia),
        ("solotodo_monitores", solotodo_monitores),
        ("travel_monitores", travel_monitores),
        ("tuganga_computacion", tuganga_computacion),
        ("descuentosrata", descuentosrata),
    ]
    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "query": "monitor",
        "output_dir": str(OUT_DIR),
        "runs": [],
    }
    for name, fn in sources:
        payload = run_source(name, fn)
        summary["runs"].append({
            "name": name,
            "ok": payload.get("ok"),
            "count": len(payload.get("items") or []),
            "output_file": payload.get("output_file"),
            "elapsed_seconds": payload.get("elapsed_seconds"),
            "error": payload.get("error"),
        })
    write_json("_summary", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

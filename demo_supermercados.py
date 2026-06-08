#!/usr/bin/env python3
from __future__ import annotations

"""
CLI de prueba y exportacion JSON para los scrapers de supermercado.

Uso:
    # Listar categorias de una tienda
    python demo_supermercados.py categorias --store jumbo

    # Extraer una categoria y exportar a JSON (mismo formato del proyecto)
    python demo_supermercados.py extraer --store jumbo --category 1000 --limit 60

    # Extraer en varias tiendas a la vez
    python demo_supermercados.py extraer --store jumbo,unimarc --category despensa --limit 40

Genera, igual que global_search.py:
    exports/super_<store>_<categoria>_<timestamp>/<store>.json   (por tienda)
    exports/super_..._/all_results.json                          (combinado)
    exports/..._/_summary.json                                   (resumen)

No requiere instalar nada (solo stdlib). Necesita acceso a internet para
llegar a los sitios de los supermercados.
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for sub in ("vtex_scraper", "lider_scraper", "tottus_scraper"):
    path = ROOT / sub
    if path.is_dir():
        sys.path.insert(0, str(path))

import registry  # noqa: E402  (vive en este mismo directorio)


def _safe_name(text: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in (text or "").strip().lower())
    return cleaned.strip("_") or "todo"


def cmd_categorias(args: argparse.Namespace) -> None:
    module = registry.get_module(args.store)
    categories = module.fetch_categories()
    print(f"[{args.store}] {len(categories)} categorias:")
    for cat in categories:
        print(f"  {cat['id']:<28} {cat['label']}")


def _run_store(source: str, category: str, query: str, limit: int, scan_scope: str) -> dict:
    module = registry.get_module(source)
    started = time.perf_counter()
    kwargs = {"category_id": category} if category else {}
    items, meta = module.collect_results(
        query=query, limit=limit, scan_scope=scan_scope, **kwargs
    )
    items = module.apply_filters(items)
    return {
        "source": source,
        "query": query,
        "ok": True,
        "count": len(items),
        "items": items,
        "meta": meta,
        "elapsed_seconds": round(time.perf_counter() - started, 2),
    }


def cmd_extraer(args: argparse.Namespace) -> None:
    sources = [s.strip() for s in args.store.split(",") if s.strip()]
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    label = _safe_name(args.category or args.query)
    output_dir = ROOT / "exports" / f"super_{'-'.join(sources)}_{label}_{stamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    merged: list[dict] = []
    runs: list[dict] = []
    for source in sources:
        try:
            payload = _run_store(source, args.category, args.query, args.limit, args.scope)
        except Exception as exc:  # noqa: BLE001
            payload = {"source": source, "ok": False, "count": 0, "items": [], "error": str(exc)}
        path = output_dir / f"{source}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        payload["output_file"] = str(path)
        for item in payload.get("items") or []:
            merged.append({"source": source, **item})
        warn = (payload.get("meta") or {}).get("warning") or payload.get("error")
        print(f"  [{source}] {payload.get('count', 0)} productos" + (f"  ! {warn}" if warn else ""))
        runs.append({"source": source, "ok": payload.get("ok"), "count": payload.get("count", 0),
                     "output_file": str(path), "warning": warn})

    (output_dir / "all_results.json").write_text(
        json.dumps(merged, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "query": args.query,
        "category": args.category,
        "sources": sources,
        "total_count": len(merged),
        "output_dir": str(output_dir),
        "runs": runs,
    }
    (output_dir / "_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nTotal: {len(merged)} productos -> {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrapers de supermercado por categoria")
    sub = parser.add_subparsers(dest="command", required=True)

    p_cat = sub.add_parser("categorias", help="Listar categorias de una tienda")
    p_cat.add_argument("--store", required=True, help="jumbo|santaisabel|unimarc|alvi|lider|acuenta|tottus")
    p_cat.set_defaults(func=cmd_categorias)

    p_ext = sub.add_parser("extraer", help="Extraer productos por categoria y exportar JSON")
    p_ext.add_argument("--store", required=True, help="Una o varias tiendas separadas por coma")
    p_ext.add_argument("--category", default="", help="id de categoria (ver comando 'categorias')")
    p_ext.add_argument("--query", default="", help="palabra clave opcional")
    p_ext.add_argument("--limit", type=int, default=60, help="maximo de productos por tienda")
    p_ext.add_argument("--scope", default="complete", help="complete|fast")
    p_ext.set_defaults(func=cmd_extraer)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

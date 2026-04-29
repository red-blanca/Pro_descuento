from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRAPER = ROOT / "mercadolibre.py"


@dataclass
class QueryResult:
    name: str
    items: list[dict[str, Any]]
    json_path: Path
    xlsx_path: Path | None


def extract_json(stdout_text: str) -> list[dict[str, Any]]:
    start = stdout_text.find("[")
    end = stdout_text.rfind("]")
    if start < 0 or end < 0 or end <= start:
        return []
    return json.loads(stdout_text[start : end + 1])


def parse_price_value(price_text: str | None) -> int | None:
    if not price_text:
        return None
    digits = "".join(ch for ch in str(price_text) if ch.isdigit())
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def score_item(item: dict[str, Any]) -> tuple[int, int]:
    discount = int(item.get("discount_percent") or 0)
    price = parse_price_value(item.get("price")) or 10**12
    return (discount, -price)


def build_cmd(base_country: str, cfg: dict[str, Any], out_json: Path, out_xlsx: Path | None, cookie: str | None) -> list[str]:
    terms = str(cfg.get("terms", "")).strip()
    if not terms:
        raise ValueError(f"Consulta '{cfg.get('name','sin_nombre')}' sin terms")

    cmd = [sys.executable, str(SCRAPER)] + terms.split()
    cmd += ["--country", str(cfg.get("country", base_country))]

    if bool(cfg.get("all_results", True)):
        cmd.append("--all-results")

    cmd += ["--max-pages", str(int(cfg.get("max_pages", 0)))]
    cmd += ["--min-price", str(max(0, int(cfg.get("min_price", 0))))]
    cmd += ["--max-price", str(max(0, int(cfg.get("max_price", 0))))]
    cmd += ["--min-discount", str(max(0, min(100, int(cfg.get("min_discount", 0)))))]

    condition = str(cfg.get("condition", "any")).strip()
    if condition != "any":
        cmd += ["--condition", condition]

    for w in cfg.get("include_words", []):
        w = str(w).strip()
        if w:
            cmd += ["--include-word", w]

    for w in cfg.get("exclude_words", []):
        w = str(w).strip()
        if w:
            cmd += ["--exclude-word", w]

    if bool(cfg.get("sort_price", True)):
        cmd.append("--sort-price")

    if bool(cfg.get("include_international", False)):
        cmd.append("--include-international")

    if cookie:
        cmd += ["--cookie", cookie]

    cmd += ["--json"]

    if out_xlsx is not None:
        cmd += ["--export-xlsx", str(out_xlsx)]

    return cmd


def run_query(base_country: str, cfg: dict[str, Any], run_dir: Path, cookie: str | None) -> QueryResult:
    name = str(cfg.get("name", "query")).strip() or "query"
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)
    json_path = run_dir / f"{safe_name}.json"
    xlsx_path = run_dir / f"{safe_name}.xlsx" if bool(cfg.get("export_xlsx", True)) else None

    cmd = build_cmd(base_country, cfg, json_path, xlsx_path, cookie)
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        timeout=3600,
        check=False,
    )

    if proc.returncode != 0:
        raise RuntimeError(
            f"Error en '{name}' (code={proc.returncode})\nSTDERR:\n{proc.stderr}\nSTDOUT:\n{proc.stdout}"
        )

    items = extract_json(proc.stdout)
    json_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    if xlsx_path is not None and not xlsx_path.exists():
        xlsx_path = None

    return QueryResult(name=name, items=items, json_path=json_path, xlsx_path=xlsx_path)


def write_summary(results: list[QueryResult], out_path: Path) -> None:
    lines: list[str] = []
    lines.append("# Resumen diario MercadoLibre")
    lines.append("")
    lines.append(f"Generado: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")

    all_items: list[dict[str, Any]] = []
    for r in results:
        all_items.extend(r.items)

    ranked = sorted(all_items, key=score_item, reverse=True)[:20]

    lines.append("## Totales por busqueda")
    lines.append("")
    for r in results:
        lines.append(f"- {r.name}: {len(r.items)} resultados")

    lines.append("")
    lines.append("## Top 20 productos (descuento alto + precio bajo)")
    lines.append("")
    lines.append("| # | Titulo | Precio | Descuento | Estado | Link |")
    lines.append("|---|---|---|---|---|---|")

    state_map = {"new": "Nuevo", "used": "Usado", "reconditioned": "Reacondicionado"}
    for idx, item in enumerate(ranked, start=1):
        title = str(item.get("title", "")).replace("|", " ")
        price = str(item.get("price") or "N/D")
        discount = f"{item.get('discount_percent')}%" if item.get("discount_percent") is not None else "0%"
        state = state_map.get(str(item.get("condition") or "").lower(), "N/D")
        link = str(item.get("link") or "")
        lines.append(f"| {idx} | {title} | {price} | {discount} | {state} | {link} |")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ejecuta busquedas diarias y genera artefactos")
    parser.add_argument("--config", default=str(ROOT / "automation" / "searches.json"))
    parser.add_argument("--output-dir", default=str(ROOT / "automation" / "runs"))
    parser.add_argument("--cookie", default=None, help="Cookie header opcional")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"No existe config: {config_path}")
        return 2

    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    base_country = str(cfg.get("country", "cl"))
    queries = cfg.get("queries", [])
    if not queries:
        print("Config sin queries")
        return 2

    run_stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = Path(args.output_dir) / run_stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    cookie = args.cookie or None

    results: list[QueryResult] = []
    for q in queries:
        result = run_query(base_country, q, run_dir, cookie)
        results.append(result)

    merged = []
    for r in results:
        for item in r.items:
            merged.append({"query": r.name, **item})

    (run_dir / "all_results.json").write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_summary(results, run_dir / "summary.md")

    print(f"Run listo: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
SCRAPER = ROOT / "facebook_marketplace.py"


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


def build_cmd(
    base_marketplace_path: str,
    base_location_query: str,
    base_radius_km: int,
    base_country_code: str,
    cfg: dict[str, Any],
    storage_state: str | None,
) -> list[str]:
    terms = str(cfg.get("terms", "")).strip()
    if not terms:
        raise ValueError(f"Consulta '{cfg.get('name', 'sin_nombre')}' sin terms")

    cmd = [sys.executable, str(SCRAPER)] + terms.split()
    cmd += ["--marketplace-path", str(cfg.get("marketplace_path", base_marketplace_path))]
    cmd += ["--limit", str(max(1, int(cfg.get("limit", 60))))]
    cmd += ["--scroll-limit", str(max(1, int(cfg.get("scroll_limit", 24))))]
    cmd += ["--min-price", str(max(0, int(cfg.get("min_price", 0))))]
    cmd += ["--max-price", str(max(0, int(cfg.get("max_price", 0))))]
    cmd += ["--location-query", str(cfg.get("location_query", base_location_query))]
    cmd += ["--radius-km", str(max(0, int(cfg.get("radius_km", base_radius_km))))]
    cmd += ["--country-code", str(cfg.get("country_code", base_country_code))]
    if storage_state:
        cmd += ["--storage-state", storage_state]
    for word in cfg.get("include_words", []):
        token = str(word).strip()
        if token:
            cmd += ["--include-word", token]
    for word in cfg.get("exclude_words", []):
        token = str(word).strip()
        if token:
            cmd += ["--exclude-word", token]
    return cmd


def run_query(
    base_marketplace_path: str,
    base_location_query: str,
    base_radius_km: int,
    base_country_code: str,
    cfg: dict[str, Any],
    run_dir: Path,
    storage_state: str | None,
) -> QueryResult:
    name = str(cfg.get("name", "query")).strip() or "query"
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)
    json_path = run_dir / f"{safe_name}.json"
    xlsx_path = run_dir / f"{safe_name}.xlsx" if bool(cfg.get("export_xlsx", True)) else None

    base_cmd = build_cmd(
        base_marketplace_path,
        base_location_query,
        base_radius_km,
        base_country_code,
        cfg,
        storage_state,
    )
    cmd = base_cmd + ["--json"]
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
    if xlsx_path is not None:
        export_proc = subprocess.run(
            base_cmd + ["--export-xlsx", str(xlsx_path)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=3600,
            check=False,
        )
        if export_proc.returncode != 0 or not xlsx_path.exists():
            xlsx_path = None
    return QueryResult(name=name, items=items, json_path=json_path, xlsx_path=xlsx_path)


def write_summary(results: list[QueryResult], out_path: Path) -> None:
    lines: list[str] = []
    lines.append("# Resumen diario Facebook Marketplace")
    lines.append("")
    lines.append(f"Generado: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")
    lines.append("## Totales por busqueda")
    lines.append("")
    for result in results:
        lines.append(f"- {result.name}: {len(result.items)} resultados")

    lines.append("")
    lines.append("## Primeros resultados")
    lines.append("")
    lines.append("| # | Busqueda | Titulo | Precio | Ubicacion | Link |")
    lines.append("|---|---|---|---|---|---|")
    index = 1
    for result in results:
        for item in result.items[:10]:
            title = str(item.get("title", "")).replace("|", " ")
            price = str(item.get("price") or "N/D")
            location = str(item.get("location") or "").replace("|", " ")
            link = str(item.get("link") or "")
            lines.append(f"| {index} | {result.name} | {title} | {price} | {location} | {link} |")
            index += 1
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ejecuta busquedas diarias y genera artefactos")
    parser.add_argument("--config", default=str(ROOT / "automation" / "searches.json"))
    parser.add_argument("--output-dir", default=str(ROOT / "automation" / "runs"))
    parser.add_argument("--storage-state", default=None, help="Archivo storage state de Playwright")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"No existe config: {config_path}")
        return 2

    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    base_marketplace_path = str(cfg.get("marketplace_path", "curico"))
    base_location_query = str(cfg.get("location_query", "Curico, Maule, Chile"))
    base_radius_km = int(cfg.get("radius_km", 12))
    base_country_code = str(cfg.get("country_code", "CL"))
    queries = cfg.get("queries", [])
    if not queries:
        print("Config sin queries")
        return 2

    run_stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = Path(args.output_dir) / run_stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    results: list[QueryResult] = []
    for query in queries:
        result = run_query(
            base_marketplace_path,
            base_location_query,
            base_radius_km,
            base_country_code,
            query,
            run_dir,
            args.storage_state,
        )
        results.append(result)

    merged: list[dict[str, Any]] = []
    for result in results:
        for item in result.items:
            merged.append({"query": result.name, **item})

    (run_dir / "all_results.json").write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_summary(results, run_dir / "summary.md")
    print(f"Run listo: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

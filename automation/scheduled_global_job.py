from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import global_search


DEFAULT_CONFIG = ROOT / "automation" / "searches.json"
DEFAULT_OUTPUT_DIR = ROOT / "automation" / "results"
GROUP_NAMES = ("usado", "nuevo")


def _load_config(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    query = str(raw.get("query") or "").strip()
    if not query:
        raise ValueError("La configuracion necesita un termino de busqueda.")

    groups = raw.get("groups")
    if not isinstance(groups, dict):
        raise ValueError("La configuracion necesita el objeto groups.")
    for name in GROUP_NAMES:
        group = groups.get(name)
        if not isinstance(group, dict) or not group.get("sources"):
            raise ValueError(f"El grupo '{name}' necesita fuentes.")
    return raw


def _group_config(raw: dict[str, Any], group_name: str) -> dict[str, Any]:
    common = {
        key: value
        for key, value in raw.items()
        if key not in {"groups"}
    }
    common.update(raw["groups"][group_name])
    return common


def _output_payload(group_name: str, result: dict[str, Any]) -> dict[str, Any]:
    sources = []
    for run in result.get("runs", []):
        sources.append({key: value for key, value in run.items() if key != "output_file"})
    return {
        "group": group_name,
        "created_at": result.get("created_at"),
        "query": result.get("query"),
        "total_count": result.get("total_count", 0),
        "elapsed_seconds": result.get("elapsed_seconds", 0),
        "sources": sources,
        "items": result.get("items", []),
    }


def run(config_path: Path, output_dir: Path) -> list[Path]:
    raw = _load_config(config_path)
    stamp = datetime.now(ZoneInfo("America/Santiago")).strftime("%Y-%m-%d_%H-%M-%S")
    query = global_search._safe_name(str(raw["query"]))
    written: list[Path] = []

    ml_cookie = os.getenv("ML_COOKIE", "").strip()
    if ml_cookie:
        import mercadolibre

        mercadolibre.configure_cookie_header(ml_cookie, None)

    for group_name in GROUP_NAMES:
        with tempfile.TemporaryDirectory(prefix=f"prodescuento-{group_name}-") as temp_dir:
            result = global_search.run_global_search(
                _group_config(raw, group_name),
                output_base=Path(temp_dir),
                include_by_source=False,
            )

        group_dir = output_dir / group_name
        group_dir.mkdir(parents=True, exist_ok=True)
        output_path = group_dir / f"{query}_{group_name}_{stamp}.json"
        output_path.write_text(
            json.dumps(_output_payload(group_name, result), ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        written.append(output_path)
        print(f"{group_name}: {result.get('total_count', 0)} resultados -> {output_path}")

    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Ejecuta las busquedas conjuntas programadas.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    run(Path(args.config), Path(args.output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

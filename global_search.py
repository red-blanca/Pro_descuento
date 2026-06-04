from __future__ import annotations

import json
import os
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parent


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


MAX_ITEMS_PER_SOURCE_CAP = max(1, _env_int("GLOBAL_MAX_ITEMS_PER_SOURCE", 10000))

for module_dir in [
    ROOT,
    ROOT / "facebook_marketplace",
    ROOT / "pulga",
    ROOT / "knasta_scraper",
    ROOT / "solotodo_scraper",
    ROOT / "travel_scraper",
    ROOT / "tuganga_scraper",
    ROOT / "descuentosrata_scraper",
    ROOT / "pcfactory_scraper",
]:
    module_path = str(module_dir)
    if module_path not in sys.path:
        sys.path.insert(0, module_path)


DEFAULT_SOURCES = [
    "mercadolibre",
    "facebook_marketplace",
    "pulga",
    "knasta",
    "solotodo",
    "travel",
    "tuganga",
    "descuentosrata",
    "pcfactory",
]


def _safe_name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value.strip())
    return cleaned.strip("_")[:60] or "busqueda"


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    return value


def _dedupe_key(item: dict[str, Any]) -> str:
    for key in ("link", "url", "permalink", "id", "sku"):
        value = item.get(key)
        if value:
            return str(value)
    return json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)


def _filter_words(
    items: list[dict[str, Any]],
    include_words: list[str],
    exclude_words: list[str],
    strict: bool = False,
    smart_filter: bool = True,
    query: str = "",
) -> list[dict[str, Any]]:
    import re
    import unicodedata

    def normalize(v: str) -> str:
        normalized = unicodedata.normalize("NFKD", str(v))
        return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower().strip()

    include = [normalize(w) for w in include_words if str(w).strip()]
    exclude = [normalize(w) for w in exclude_words if str(w).strip()]
    
    STRONG_ACCESSORIES = {
        "repuesto", "carcasa", "funda", "bolso", "estuche", "mica", "protector",
        "cargador", "cable", "servicio", "reparacion", "arreglo", "tecnico",
        "manual", "caja", "sticker", "calcomania", "mini", "soporte", "adaptador", 
        "vidrio", "templado", "lamina", "desarme", "bisagra", "flex", "cooler", 
        "ventilador", "pin", "jack", "motherboard", "correa", "mouse", "raton", 
        "audifono", "audifonos", "auricular", "auriculares", "mochila", "maletin", 
        "maleta", "parlante", "parlantes", "microfono", "tablet", "ipad", "consola", 
        "nintendo", "xbox", "playstation", "ps4", "ps5", "escritorio", "torre", 
        "gabinete", "impresora", "router", "candado", "base", "chatarra"
    }
    
    WEAK_ACCESSORIES = {
        "pantalla", "teclado", "bateria", "placa", "memoria", "ram", "ssd", "disco", "hdd", "pantallas", "teclados", "baterias", "placas", "memorias", "discos"
    }

    filtered: list[dict[str, Any]] = []
    for item in items:
        fields = ["title", "name", "brand", "store", "category", "description"]
        haystack_raw = " ".join(str(item.get(k) or "") for k in fields)
        haystack = normalize(haystack_raw)
        
        def has_term(text: str, term: str, whole: bool) -> bool:
            if not whole:
                return term in text
            return bool(re.search(rf"\b{re.escape(term)}\b", text))

        if include and not all(has_term(haystack, w, strict) for w in include):
            continue
        if exclude and any(has_term(haystack, w, False) for w in exclude):
            continue
            
        if smart_filter:
            title_lc = normalize(item.get("title") or item.get("name") or "")
            query_words = set(include) | set(normalize(query).split())
            title_words_list = title_lc.split()
            title_words = set(title_words_list)
            
            # Check strong accessories
            found_strong = title_words & STRONG_ACCESSORIES
            if found_strong and not (found_strong & query_words):
                if "para" in found_strong or "compatible" in found_strong or " para " in title_lc or " compatible con " in title_lc:
                    continue
                    
                is_bundle = any(w in title_words for w in ["+", "mas", "regalo", "incluye", "gratis", "con", "y"]) or "+" in title_lc
                if not is_bundle:
                    continue
                
                first_acc_idx = min([title_words_list.index(w) for w in found_strong if w in title_words_list], default=999)
                first_query_idx = min([title_words_list.index(w) for w in query_words if w in title_words_list], default=999)
                if first_acc_idx < first_query_idx:
                    continue
                    
            # Check weak accessories (only filter if they are the first word, or used with "para")
            if title_words_list:
                first_word = title_words_list[0]
                if first_word in WEAK_ACCESSORIES and first_word not in query_words:
                    continue
                
                found_weak = title_words & WEAK_ACCESSORIES
                if found_weak and not (found_weak & query_words):
                    if " para " in title_lc or " compatible con " in title_lc:
                        continue

        filtered.append(item)
    return filtered


def _limit_for(scope: str, max_items: int, fast_default: int) -> int:
    if scope == "complete":
        return max(1, min(max_items, MAX_ITEMS_PER_SOURCE_CAP, 10000))
    return max(1, min(max_items, fast_default))


def _source_payload(source: str, query: str, items: list[dict[str, Any]], meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": source,
        "query": query,
        "count": len(items),
        "items": items,
        **meta,
    }


def _run_mercadolibre(cfg: dict[str, Any]) -> dict[str, Any]:
    import mercadolibre as ml

    cookie_file = ROOT / "cookies.txt"
    if cookie_file.exists():
        ml.configure_cookie_header(None, str(cookie_file))

    scope = cfg["scan_scope"]
    items = ml.collect_results(
        query=cfg["query"],
        country=cfg["country"],
        limit=_limit_for(scope, cfg["max_items_per_source"], 80),
        fetch_all=scope == "complete",
        max_pages=0 if scope == "complete" else 2,
        exclude_international=not cfg["include_international"],
        min_price=cfg["min_price"],
        max_price=cfg["max_price"],
        min_discount=cfg["min_discount"],
        sort_price=cfg["sort_price"],
        condition_filter=cfg["mercadolibre_condition"],
        search_url=cfg["mercadolibre_search_url"] or None,
        timeout=30,
        quiet=True,
    )
    items = ml.apply_filters(
        items,
        min_price=cfg["min_price"],
        max_price=cfg["max_price"],
        word=cfg["mercadolibre_word"],
        include_words=cfg["include_words"],
        min_discount=cfg["min_discount"],
        exclude_words=cfg["exclude_words"],
        strict=cfg.get("strict_mode", False),
        smart_filter=cfg.get("smart_filter", True),
        query=cfg["query"],
    )
    return _source_payload("mercadolibre", cfg["query"], items, {"condition": cfg["mercadolibre_condition"]})


def _run_facebook(cfg: dict[str, Any]) -> dict[str, Any]:
    import facebook_api as fb

    cookies = fb.load_cookie_profiles()
    opts = fb.SearchOptions(
        query=cfg["query"],
        marketplace_path=cfg["facebook_marketplace_path"],
        limit=_limit_for(cfg["scan_scope"], min(cfg["max_items_per_source"], 500), 60),
        max_pages=8 if cfg["scan_scope"] == "complete" else 2,
        min_price=cfg["min_price"],
        max_price=cfg["max_price"],
        word=cfg["facebook_word"],
        include_words=cfg["include_words"],
        exclude_words=cfg["exclude_words"],
        location_query=cfg["facebook_location_query"],
        latitude=cfg["facebook_latitude"],
        longitude=cfg["facebook_longitude"],
        radius_km=cfg["facebook_radius_km"],
        include_talca=cfg["facebook_include_talca"],
        country_code="CL",
    )
    result = fb.execute_search(opts, cookies)
    warnings = list(result.filter_breakdown.get("warnings") or [])
    return _source_payload(
        "facebook_marketplace",
        cfg["query"],
        result.items,
        {
            "total_matches": result.total_matches,
            "captured_raw": result.captured_raw,
            "filter_breakdown": result.filter_breakdown,
            "warning": " ".join(str(w) for w in warnings if str(w).strip()),
        },
    )


def _run_pulga(cfg: dict[str, Any]) -> dict[str, Any]:
    import pulga

    items, total = pulga.collect_results(
        query=cfg["query"],
        category=cfg["pulga_category"] or None,
        limit=_limit_for(cfg["scan_scope"], cfg["max_items_per_source"], 80),
        fetch_all=cfg["scan_scope"] == "complete",
        max_pages=0,
        quiet=True,
    )
    items = pulga.apply_filters(
        items,
        min_price=cfg["min_price"],
        max_price=cfg["max_price"],
        condition_filter=cfg["pulga_condition"],
        word=cfg["pulga_word"],
        include_words=cfg["include_words"],
        exclude_words=cfg["exclude_words"],
        city_filter=cfg["pulga_city"],
    )
    items = _filter_words(
        items, 
        cfg["include_words"], 
        cfg["exclude_words"],
        strict=cfg.get("strict_mode", False),
        smart_filter=cfg.get("smart_filter", True),
        query=cfg["query"]
    )
    return _source_payload(
        "pulga",
        cfg["query"],
        items,
        {"category": cfg["pulga_category"], "total_available": total},
    )


def _run_knasta(cfg: dict[str, Any]) -> dict[str, Any]:
    import knasta_api as knasta

    opts = knasta.SearchOptions(
        query=cfg["query"],
        retails=cfg["knasta_retails"],
        knastaday=cfg["knasta_knastaday"],
        category=cfg["knasta_category"],
        limit=_limit_for(cfg["scan_scope"], cfg["max_items_per_source"], 120),
        max_pages=200 if cfg["scan_scope"] == "complete" else 3,
        scan_scope=cfg["scan_scope"],
    )
    result = knasta.execute_search(opts)
    items = _filter_words(
        result.items, 
        cfg["include_words"], 
        cfg["exclude_words"],
        strict=cfg.get("strict_mode", False),
        smart_filter=cfg.get("smart_filter", True),
        query=cfg["query"]
    )
    return _source_payload(
        "knasta",
        cfg["query"],
        items,
        {
            "category": cfg["knasta_category"],
            "total_matches": result.total_matches,
            "pages_fetched": result.pages_fetched,
            "fetched_raw": result.fetched_raw,
            "total_pages": result.total_pages,
        },
    )


def _run_solotodo(cfg: dict[str, Any]) -> dict[str, Any]:
    import solotodo

    category_id = cfg["solotodo_category_id"]
    items, meta = solotodo.collect_browse_results(
        query=cfg["query"],
        category_id=category_id if category_id else None,
        country_id=cfg["solotodo_country_id"],
        ordering=cfg["solotodo_ordering"],
        limit=_limit_for(cfg["scan_scope"], cfg["max_items_per_source"], 80),
        fetch_all=cfg["scan_scope"] == "complete",
    )
    items = solotodo.apply_filters(
        items,
        min_price=cfg["min_price"],
        max_price=cfg["max_price"],
        include_words=cfg["include_words"],
        exclude_words=cfg["exclude_words"],
    )
    items = _filter_words(
        items, 
        cfg["include_words"], 
        cfg["exclude_words"],
        strict=cfg.get("strict_mode", False),
        smart_filter=cfg.get("smart_filter", True),
        query=cfg["query"]
    )
    return _source_payload(
        "solotodo",
        cfg["query"],
        items,
        {"category_id": cfg["solotodo_category_id"], "country_id": cfg["solotodo_country_id"], "ordering": cfg["solotodo_ordering"], "meta": meta},
    )


def _run_travel(cfg: dict[str, Any]) -> dict[str, Any]:
    import travel

    items, meta = travel.collect_results(
        query=cfg["query"],
        category_id=cfg["travel_category_id"],
        ordering=cfg["travel_ordering"],
        limit=_limit_for(cfg["scan_scope"], cfg["max_items_per_source"], 80),
        fetch_all=cfg["scan_scope"] == "complete",
    )
    items = travel.apply_filters(
        items,
        min_price=cfg["min_price"],
        max_price=cfg["max_price"],
        include_words=cfg["include_words"],
        exclude_words=cfg["exclude_words"],
        ordering=cfg["travel_ordering"],
    )
    items = _filter_words(
        items, 
        cfg["include_words"], 
        cfg["exclude_words"],
        strict=cfg.get("strict_mode", False),
        smart_filter=cfg.get("smart_filter", True),
        query=cfg["query"]
    )
    return _source_payload("travel", cfg["query"], items, {"category_id": cfg["travel_category_id"], "ordering": cfg["travel_ordering"], "meta": meta})


def _run_tuganga(cfg: dict[str, Any]) -> dict[str, Any]:
    import tuganga_api as tuganga

    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    runs: list[dict[str, Any]] = []
    categories = cfg["tuganga_categories"] or [""]
    per_category_limit = max(1, _limit_for(cfg["scan_scope"], cfg["max_items_per_source"], 80) // len(categories))

    for category in categories:
        opts = tuganga.SearchOptions(
            query=cfg["query"],
            mode=cfg["tuganga_mode"],
            stores=cfg["tuganga_stores"],
            category=category,
            min_discount=cfg["min_discount"],
            min_price=cfg["min_price"],
            max_price=cfg["max_price"],
            only_available=cfg["tuganga_only_available"],
            sort=cfg["tuganga_sort"],
            limit=per_category_limit,
            max_pages=200 if cfg["scan_scope"] == "complete" else 3,
            scan_scope=cfg["scan_scope"],
        )
        result = tuganga.execute_search(opts)
        runs.append(_plain(result))
        for item in result.items:
            key = _dedupe_key(item)
            if key in seen:
                continue
            seen.add(key)
            items.append(item)

    items = _filter_words(
        items, 
        cfg["include_words"], 
        cfg["exclude_words"],
        strict=cfg.get("strict_mode", False),
        smart_filter=cfg.get("smart_filter", True),
        query=cfg["query"]
    )
    return _source_payload(
        "tuganga",
        cfg["query"],
        items,
        {"mode": cfg["tuganga_mode"], "stores": cfg["tuganga_stores"], "categories": categories, "runs": runs},
    )


def _run_descuentosrata(cfg: dict[str, Any]) -> dict[str, Any]:
    import descuentosrata_api as dr

    query = "" if cfg["descuentosrata_all"] else cfg["query"]
    result = dr.execute_search(
        dr.SearchOptions(
            query=query,
            min_price=cfg["min_price"],
            max_price=cfg["max_price"],
            limit=cfg["descuentosrata_limit"],
        )
    )
    items = _filter_words(
        result.items, 
        cfg["include_words"], 
        cfg["exclude_words"],
        strict=cfg.get("strict_mode", False),
        smart_filter=cfg.get("smart_filter", True),
        query=cfg["query"]
    )
    return _source_payload(
        "descuentosrata",
        query,
        items,
        {"total_matches": result.total_matches, "search_url": result.search_url, "query_mode": "all" if cfg["descuentosrata_all"] else "filtered"},
    )


def _run_pcfactory(cfg: dict[str, Any]) -> dict[str, Any]:
    import pcfactory

    items, meta = pcfactory.collect_results(
        query=cfg["query"],
        limit=_limit_for(cfg["scan_scope"], cfg["max_items_per_source"], 80),
        scan_scope=cfg["scan_scope"],
    )
    items = pcfactory.apply_filters(
        items,
        min_price=cfg["min_price"],
        max_price=cfg["max_price"],
        word=cfg["pcfactory_word"],
        include_words=cfg["include_words"],
        exclude_words=cfg["exclude_words"],
    )
    return _source_payload("pcfactory", cfg["query"], items, meta)


RUNNERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "mercadolibre": _run_mercadolibre,
    "facebook_marketplace": _run_facebook,
    "pulga": _run_pulga,
    "knasta": _run_knasta,
    "solotodo": _run_solotodo,
    "travel": _run_travel,
    "tuganga": _run_tuganga,
    "descuentosrata": _run_descuentosrata,
    "pcfactory": _run_pcfactory,
}


def _run_source_timed(source: str, cfg: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    payload = RUNNERS[source](cfg)
    payload["elapsed_seconds"] = round(time.perf_counter() - started, 2)
    return payload


def _raw_int(raw: dict[str, Any], key: str, default: int) -> int:
    """Respect 0 as a valid value (Todas las categorias en SoloTodo)."""
    if key not in raw:
        return default
    try:
        return int(raw.get(key))
    except (TypeError, ValueError):
        return default


def _raw_category_str(raw: dict[str, Any], key: str, default: str) -> str:
    """Respect '' as Todas las categorias (no reemplazar por default)."""
    if key not in raw:
        return default
    return str(raw.get(key) if raw.get(key) is not None else "").strip()


def build_config(raw: dict[str, Any]) -> dict[str, Any]:
    scope = str(raw.get("scan_scope") or "fast").strip()
    if scope not in {"fast", "complete"}:
        scope = "fast"
    sources = [str(s).strip() for s in raw.get("sources", DEFAULT_SOURCES) if str(s).strip() in RUNNERS]
    query = str(raw.get("query") or "").strip()
    pulga_category = _raw_category_str(raw, "pulga_category", "tecnologia")
    knasta_category = _raw_category_str(raw, "knasta_category", "")
    solotodo_category_id = _raw_int(raw, "solotodo_category_id", 0)
    travel_category_id = _raw_category_str(raw, "travel_category_id", "")
    tuganga_mode = str(raw.get("tuganga_mode") or "all_offers").strip() or "all_offers"
    if query and tuganga_mode != "search":
        tuganga_mode = "search"
    return {
        "query": query,
        "sources": sources or DEFAULT_SOURCES,
        "scan_scope": scope,
        "country": str(raw.get("country") or "cl").strip() or "cl",
        "max_items_per_source": max(1, min(int(raw.get("max_items_per_source") or 10000), MAX_ITEMS_PER_SOURCE_CAP, 10000)),
        "min_price": max(0, int(raw.get("min_price") or 0)),
        "max_price": max(0, int(raw.get("max_price") or 0)),
        "min_discount": max(0, min(100, int(raw.get("min_discount") or 0))),
        "include_words": [str(w).strip() for w in raw.get("include_words", []) if str(w).strip()],
        "exclude_words": [str(w).strip() for w in raw.get("exclude_words", []) if str(w).strip()],
        "strict_mode": bool(raw.get("strict_mode", False)),
        "smart_filter": bool(raw.get("smart_filter", True)),
        "sort_price": bool(raw.get("sort_price", False)),
        "include_international": bool(raw.get("include_international", False)),
        "mercadolibre_word": str(raw.get("mercadolibre_word") or "").strip(),
        "mercadolibre_search_url": str(raw.get("mercadolibre_search_url") or "").strip(),
        "mercadolibre_condition": str(raw.get("mercadolibre_condition") or "used").strip() or "used",
        "facebook_word": str(raw.get("facebook_word") or "").strip(),
        "facebook_marketplace_path": str(raw.get("facebook_marketplace_path") or "curico").strip() or "curico",
        "facebook_location_query": str(raw.get("facebook_location_query") or "Curico, Maule, Chile").strip(),
        "facebook_latitude": raw.get("facebook_latitude", -34.98749193781055),
        "facebook_longitude": raw.get("facebook_longitude", -71.24675716218236),
        "facebook_radius_km": max(1, int(raw.get("facebook_radius_km") or 35)),
        "facebook_include_talca": bool(raw.get("facebook_include_talca", True)),
        "pulga_category": pulga_category or "",
        "pulga_condition": str(raw.get("pulga_condition") or "any").strip() or "any",
        "pulga_city": str(raw.get("pulga_city") or "").strip(),
        "pulga_word": str(raw.get("pulga_word") or "").strip(),
        "knasta_category": knasta_category,
        "knasta_retails": [str(r).strip() for r in raw.get("knasta_retails", []) if str(r).strip()],
        "knasta_knastaday": max(0, int(raw.get("knasta_knastaday") or 0)),
        "solotodo_category_id": solotodo_category_id,
        "solotodo_country_id": int(raw.get("solotodo_country_id") or 1),
        "solotodo_ordering": str(raw.get("solotodo_ordering") or "offer_price_usd").strip() or "offer_price_usd",
        "travel_category_id": travel_category_id,
        "travel_ordering": str(raw.get("travel_ordering") or "relevance").strip() or "relevance",
        "tuganga_mode": tuganga_mode,
        "tuganga_stores": [str(s).strip() for s in raw.get("tuganga_stores", []) if str(s).strip()],
        "tuganga_categories": [str(c).strip() for c in raw.get("tuganga_categories", []) if str(c).strip()],
        "tuganga_only_available": bool(raw.get("tuganga_only_available", False)),
        "tuganga_sort": str(raw.get("tuganga_sort") or "").strip(),
        "pcfactory_word": str(raw.get("pcfactory_word") or "").strip(),
        "descuentosrata_all": bool(raw.get("descuentosrata_all", True)),
        "descuentosrata_limit": max(1, min(int(raw.get("descuentosrata_limit") or 10000), 10000)),
    }


def run_global_search(
    raw_config: dict[str, Any],
    output_base: Path | None = None,
    progress_callback: Callable[[str, dict[str, Any]], None] | None = None,
    include_by_source: bool = True,
) -> dict[str, Any]:
    cfg = build_config(raw_config)
    has_category = any([
        cfg.get("pulga_category"),
        cfg.get("knasta_category"),
        cfg.get("solotodo_category_id"),
        cfg.get("travel_category_id"),
        cfg.get("tuganga_categories"),
    ])
    if not cfg["query"] and not has_category and any(source != "descuentosrata" for source in cfg["sources"]):
        raise ValueError("Debes indicar una palabra clave o seleccionar una categoría.")

    started = time.perf_counter()
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    output_dir = (output_base or ROOT / "exports") / f"global_{_safe_name(cfg['query'])}_{stamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    by_source: dict[str, dict[str, Any]] = {}
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    with ThreadPoolExecutor(max_workers=min(3, len(cfg["sources"]))) as executor:
        futures = {executor.submit(_run_source_timed, source, cfg): source for source in cfg["sources"]}
        for future in as_completed(futures):
            source = futures[future]
            try:
                payload = future.result()
                payload["ok"] = True
            except Exception as exc:
                payload = {
                    "source": source,
                    "query": cfg["query"],
                    "ok": False,
                    "count": 0,
                    "items": [],
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                    "elapsed_seconds": 0,
                }
            path = output_dir / f"{source}.json"
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            payload["output_file"] = str(path)
            if progress_callback:
                try:
                    progress_callback(source, payload)
                except Exception:
                    pass
            for item in payload.get("items") or []:
                key = f"{source}:{_dedupe_key(item)}"
                if key in seen:
                    continue
                seen.add(key)
                merged.append({"source": source, **item})
            by_source[source] = payload if include_by_source else {
                "source": payload.get("source", source),
                "query": payload.get("query", cfg["query"]),
                "ok": payload.get("ok", False),
                "count": len(payload.get("items") or []),
                "output_file": payload.get("output_file"),
                "error": payload.get("error"),
                "warning": payload.get("warning"),
                "elapsed_seconds": payload.get("elapsed_seconds", 0),
            }

    all_path = output_dir / "all_results.json"
    all_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "query": cfg["query"],
        "scan_scope": cfg["scan_scope"],
        "output_dir": str(output_dir),
        "all_results_file": str(all_path),
        "total_count": len(merged),
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "runs": [
            {
                "source": source,
                "ok": by_source[source].get("ok", False),
                "count": len(by_source[source].get("items") or []) if "items" in by_source[source] else int(by_source[source].get("count") or 0),
                "output_file": by_source[source].get("output_file"),
                "error": by_source[source].get("error"),
                "warning": by_source[source].get("warning"),
                "elapsed_seconds": by_source[source].get("elapsed_seconds", 0),
            }
            for source in cfg["sources"]
            if source in by_source
        ],
    }
    (output_dir / "_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    result = {
        **summary,
        "items": merged,
    }
    if include_by_source:
        result["by_source"] = by_source
    return result

from __future__ import annotations

import os
import re
import hashlib
import json
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import mercadolibre as ml
import global_search
import facebook_api as fb
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "mercadolibre.py"
WEB_DIST = ROOT / "web" / "dist"
COUNT_CACHE_TTL_SECONDS = 300
_COUNT_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_LOCK = threading.Lock()

# Async job store for long-running global searches
_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()


class SearchPayload(BaseModel):
    query: str = Field(default="")
    country: str = Field(default="cl")
    all_results: bool = Field(default=True)
    max_pages: int = Field(default=0)
    min_price: int = Field(default=0)
    max_price: int = Field(default=0)
    min_discount: int = Field(default=0)
    word: str = Field(default="")
    include_words: list[str] = Field(default_factory=list)
    exclude_words: list[str] = Field(default_factory=list)
    condition: str = Field(default="any")
    sort_price: bool = Field(default=True)
    include_international: bool = Field(default=False)
    cookie_file: str = Field(default="")
    search_url: str = Field(default="")
    category_url: str = Field(default="")
    scan_scope: str = Field(default="fast")
    preview_limit: int = Field(default=200)
    strict_mode: bool = Field(default=False)
    smart_filter: bool = Field(default=True)


class GlobalSearchPayload(BaseModel):
    query: str = Field(default="")
    sources: list[str] = Field(default_factory=lambda: global_search.DEFAULT_SOURCES.copy())
    scan_scope: str = Field(default="fast")
    country: str = Field(default="cl")
    max_items_per_source: int = Field(default=10000)
    min_price: int = Field(default=0)
    max_price: int = Field(default=0)
    min_discount: int = Field(default=0)
    include_words: list[str] = Field(default_factory=list)
    exclude_words: list[str] = Field(default_factory=list)
    sort_price: bool = Field(default=False)
    include_international: bool = Field(default=False)
    mercadolibre_word: str = Field(default="")
    mercadolibre_search_url: str = Field(default="")
    mercadolibre_condition: str = Field(default="used")
    facebook_word: str = Field(default="")
    facebook_marketplace_path: str = Field(default="curico")
    facebook_location_query: str = Field(default="Curico, Maule, Chile")
    facebook_latitude: float | None = Field(default=-34.98749193781055)
    facebook_longitude: float | None = Field(default=-71.24675716218236)
    facebook_radius_km: int = Field(default=35)
    facebook_include_talca: bool = Field(default=True)
    pulga_category: str = Field(default="tecnologia")
    pulga_condition: str = Field(default="any")
    pulga_city: str = Field(default="")
    pulga_word: str = Field(default="")
    knasta_category: str = Field(default="20106")
    knasta_retails: list[str] = Field(default_factory=list)
    knasta_knastaday: int = Field(default=0)
    solotodo_category_id: int = Field(default=0)
    solotodo_country_id: int = Field(default=1)
    solotodo_ordering: str = Field(default="offer_price_usd")
    travel_category_id: str = Field(default="")
    travel_ordering: str = Field(default="relevance")
    tuganga_mode: str = Field(default="search")
    tuganga_stores: list[str] = Field(default_factory=list)
    tuganga_categories: list[str] = Field(default_factory=list)
    tuganga_only_available: bool = Field(default=False)
    tuganga_sort: str = Field(default="")
    descuentosrata_all: bool = Field(default=True)
    descuentosrata_limit: int = Field(default=10000)
    strict_mode: bool = Field(default=False)
    smart_filter: bool = Field(default=True)


app = FastAPI(title="MercadoLibre UI API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _resolve_cookie_file(cookie_file: str) -> str | None:
    raw = cookie_file.strip()
    if not raw:
        default_cookie_file = ROOT / "cookies.txt"
        return str(default_cookie_file) if default_cookie_file.exists() else None
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return str(path)


def _build_base_cmd(payload: SearchPayload) -> list[str]:
    cmd = [sys.executable, str(SCRIPT)]
    query = payload.query.strip()
    if query:
        cmd.extend(query.split())

    cmd.extend(["--country", payload.country])
    if payload.all_results:
        cmd.append("--all-results")
    cmd.extend(["--max-pages", str(payload.max_pages)])
    cmd.extend(["--min-price", str(max(0, payload.min_price))])
    cmd.extend(["--max-price", str(max(0, payload.max_price))])
    cmd.extend(["--min-discount", str(max(0, min(100, payload.min_discount)))])
    if payload.word.strip():
        cmd.extend(["--word", payload.word.strip()])
    for word in payload.include_words:
        word = str(word).strip()
        if word:
            cmd.extend(["--include-word", word])
    for word in payload.exclude_words:
        word = str(word).strip()
        if word:
            cmd.extend(["--exclude-word", word])
    if payload.condition != "any":
        cmd.extend(["--condition", payload.condition])
    if payload.sort_price:
        cmd.append("--sort-price")
    if payload.include_international:
        cmd.append("--include-international")
    cookie_file = _resolve_cookie_file(payload.cookie_file)
    if cookie_file:
        cmd.extend(["--cookie-file", cookie_file])
    if payload.search_url.strip():
        cmd.extend(["--search-url", payload.search_url.strip()])
    return cmd


def _extract_json(stdout_text: str) -> list[dict]:
    start = stdout_text.find("[")
    end = stdout_text.rfind("]")
    if start < 0 or end < 0 or end <= start:
        return []
    try:
        return json.loads(stdout_text[start : end + 1])
    except json.JSONDecodeError:
        return []


def _to_excel_preview_rows(items: list[dict]) -> list[dict]:
    state_map = {"new": "Nuevo", "used": "Usado", "reconditioned": "Reacondicionado"}
    rows: list[dict] = []
    for idx, item in enumerate(items, start=1):
        raw_condition = str(item.get("condition") or "").lower().strip()
        rows.append(
            {
                "Posicion": idx,
                "Titulo": str(item.get("title") or ""),
                "Precio": str(item.get("price") or ""),
                "Descuento": (
                    f"{item.get('discount_percent')}%"
                    if item.get("discount_percent") is not None
                    else ""
                ),
                "Estado": state_map.get(raw_condition, "N/D"),
                "Link": str(item.get("link") or ""),
            }
        )
    return rows


def _payload_cache_key(payload: SearchPayload) -> str:
    normalized = {
        "query": payload.query.strip(),
        "country": payload.country,
        "all_results": bool(payload.all_results),
        "max_pages": int(payload.max_pages),
        "min_price": int(max(0, payload.min_price)),
        "max_price": int(max(0, payload.max_price)),
        "min_discount": int(max(0, min(100, payload.min_discount))),
        "word": payload.word.strip(),
        "include_words": sorted([str(w).strip() for w in payload.include_words if str(w).strip()]),
        "exclude_words": sorted([str(w).strip() for w in payload.exclude_words if str(w).strip()]),
        "condition": payload.condition,
        "sort_price": bool(payload.sort_price),
        "include_international": bool(payload.include_international),
        "cookie_file": payload.cookie_file.strip(),
        "search_url": payload.search_url.strip(),
        "category_url": payload.category_url.strip(),
        "scan_scope": payload.scan_scope.strip(),
    }
    raw = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> dict | None:
    now = time.time()
    with _CACHE_LOCK:
        entry = _COUNT_CACHE.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if expires_at < now:
            _COUNT_CACHE.pop(key, None)
            return None
        return value


def _cache_set(key: str, value: dict) -> None:
    expires_at = time.time() + COUNT_CACHE_TTL_SECONDS
    with _CACHE_LOCK:
        _COUNT_CACHE[key] = (expires_at, value)


def _count_in_process(payload: SearchPayload) -> dict:
    ml.configure_cookie_header(None, _resolve_cookie_file(payload.cookie_file))
    condition_filter = payload.condition if payload.condition in {"any", "new", "used", "reconditioned"} else "any"
    fetch_all = bool(payload.all_results) or payload.scan_scope == "complete"
    limit = 10
    local_text_filters = bool(
        payload.word.strip()
        or [w for w in payload.include_words if str(w).strip()]
        or [w for w in payload.exclude_words if str(w).strip()]
    )
    first_url = ml.build_initial_listing_url(
        payload.query.strip(),
        payload.country,
        not bool(payload.include_international),
        max(0, int(payload.min_price)),
        max(0, int(payload.max_price)),
        max(0, min(100, int(payload.min_discount))),
        bool(payload.sort_price),
        condition_filter,
        search_url=payload.search_url.strip() or None,
        category_url=payload.category_url.strip() or None,
    )
    if not local_text_filters:
        meta = ml.search_metadata_from_url(first_url, payload.country)
        paging = meta.get("paging") or {}
        return {
            "count": int(paging.get("total") or paging.get("primary_results") or 0),
            "count_source": "mercadolibre_native",
            "pages_fetched": 1,
            "fetched_raw": len(meta.get("results") or []),
        }

    fast_limit = 5000 if fetch_all else limit
    items, meta = ml.collect_results_from_search_api(
        query=payload.query.strip(),
        country=payload.country,
        limit=fast_limit,
        fetch_all=fetch_all,
        max_pages=int(payload.max_pages),
        exclude_international=not bool(payload.include_international),
        min_price=max(0, int(payload.min_price)),
        max_price=max(0, int(payload.max_price)),
        min_discount=max(0, min(100, int(payload.min_discount))),
        sort_price=bool(payload.sort_price),
        condition_filter=condition_filter,
        search_url=payload.search_url.strip() or None,
        category_url=payload.category_url.strip() or None,
    )

    items = ml.apply_filters(
        items,
        min_price=max(0, int(payload.min_price)),
        max_price=max(0, int(payload.max_price)),
        word=payload.word.strip(),
        include_words=[str(w).strip() for w in payload.include_words if str(w).strip()],
        min_discount=max(0, min(100, int(payload.min_discount))),
        exclude_words=[str(w).strip() for w in payload.exclude_words if str(w).strip()],
    )

    if condition_filter != "any":
        items = [item for item in items if not item.get("condition") or item.get("condition") == condition_filter]
        if not fetch_all:
            items = items[:limit]

    return {
        "count": len(items),
        "count_source": "fast_filtered",
        "pages_fetched": meta.get("pages_fetched", 0),
        "fetched_raw": meta.get("fetched_raw", 0),
    }


def _applied_filters(payload: SearchPayload) -> dict:
    return {
        "query": payload.query,
        "min_price": payload.min_price,
        "max_price": payload.max_price,
        "include_words": payload.include_words,
        "exclude_words": payload.exclude_words,
        "condition": payload.condition,
        "country": payload.country,
    }


def _collect_preview_items(payload: SearchPayload, limit: int) -> tuple[list[dict], dict]:
    ml.configure_cookie_header(None, _resolve_cookie_file(payload.cookie_file))
    condition_filter = payload.condition if payload.condition in {"any", "new", "used", "reconditioned"} else "any"
    fetch_all = payload.scan_scope == "complete"
    items, meta = ml.collect_results_from_search_api(
        query=payload.query.strip(),
        country=payload.country,
        limit=limit,
        fetch_all=fetch_all,
        max_pages=int(payload.max_pages),
        exclude_international=not bool(payload.include_international),
        min_price=max(0, int(payload.min_price)),
        max_price=max(0, int(payload.max_price)),
        min_discount=max(0, min(100, int(payload.min_discount))),
        sort_price=bool(payload.sort_price),
        condition_filter=condition_filter,
        search_url=payload.search_url.strip() or None,
        category_url=payload.category_url.strip() or None,
    )
    items = ml.apply_filters(
        items,
        min_price=max(0, int(payload.min_price)),
        max_price=max(0, int(payload.max_price)),
        word=payload.word.strip(),
        include_words=[str(w).strip() for w in payload.include_words if str(w).strip()],
        min_discount=max(0, min(100, int(payload.min_discount))),
        exclude_words=[str(w).strip() for w in payload.exclude_words if str(w).strip()],
        strict=payload.strict_mode,
        smart_filter=payload.smart_filter,
    )
    if condition_filter != "any":
        items = [
            item if item.get("condition") else {**item, "condition": condition_filter}
            for item in items
            if item.get("condition") in {condition_filter, None, ""}
        ]
    if payload.sort_price:
        items = ml.sort_items_by_price(items)
    else:
        for idx, item in enumerate(items, start=1):
            item["position"] = idx
    return items[:limit], meta


@app.post("/api/count")
def count_results(payload: SearchPayload) -> dict:
    if not payload.query.strip() and not payload.search_url.strip() and not payload.category_url.strip():
        raise HTTPException(status_code=400, detail="Debes indicar búsqueda, categoría o URL exacta.")

    cache_key = _payload_cache_key(payload)
    cached = _cache_get(cache_key)
    if cached is not None:
        return {
            **cached,
            "cache_hit": True,
        }

    started = time.perf_counter()
    try:
        computed = _count_in_process(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error ejecutando scraper exacto: {exc}") from exc
    elapsed = time.perf_counter() - started
    response = {
        "count": computed["count"],
        "elapsed_seconds": round(elapsed, 2),
        "cache_hit": False,
        "count_source": computed.get("count_source", "fast"),
        "pages_fetched": computed.get("pages_fetched", 0),
        "fetched_raw": computed.get("fetched_raw", 0),
        "applied_filters": _applied_filters(payload),
    }
    _cache_set(cache_key, response)
    return response


@app.post("/api/count-exact")
def count_results_exact(payload: SearchPayload) -> dict:
    if not payload.query.strip() and not payload.search_url.strip() and not payload.category_url.strip():
        raise HTTPException(status_code=400, detail="Debes indicar búsqueda, categoría o URL exacta.")

    cache_key = f"exact:{_payload_cache_key(payload)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return {
            **cached,
            "cache_hit": True,
        }

    started = time.perf_counter()
    try:
        computed = _count_in_process(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error ejecutando scraper exacto: {exc}") from exc
    elapsed = time.perf_counter() - started
    response = {
        "count": computed["count"],
        "elapsed_seconds": round(elapsed, 2),
        "cache_hit": False,
        "count_source": computed.get("count_source", "fast"),
        "pages_fetched": computed.get("pages_fetched", 0),
        "fetched_raw": computed.get("fetched_raw", 0),
        "applied_filters": _applied_filters(payload),
    }
    _cache_set(cache_key, response)
    return response


@app.post("/api/export")
def export_results(payload: SearchPayload):
    if not payload.query.strip() and not payload.search_url.strip() and not payload.category_url.strip():
        raise HTTPException(status_code=400, detail="Debes indicar búsqueda, categoría o URL exacta.")

    limit = max(1, min(int(payload.preview_limit or 2000), 10000))
    if payload.scan_scope == "complete" or payload.all_results:
        limit = 10000
    try:
        items, _meta = _collect_preview_items(payload, limit)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error exportando: {exc}") from exc

    export_path = Path(tempfile.mktemp(prefix="ml_export_", suffix=".json"))
    export_path.write_text(json.dumps(items, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    return FileResponse(
        path=export_path,
        media_type="application/json",
        filename=f"ml_export_{int(time.time())}.json",
    )


@app.post("/api/preview")
def preview_results(payload: SearchPayload) -> dict:
    if not payload.query.strip() and not payload.search_url.strip() and not payload.category_url.strip():
        raise HTTPException(status_code=400, detail="Debes indicar búsqueda, categoría o URL exacta.")

    limit = max(1, min(int(payload.preview_limit or 200), 10000))
    started = time.perf_counter()
    try:
        items, meta = _collect_preview_items(payload, limit)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error en previsualización: {exc}") from exc
    elapsed = time.perf_counter() - started
    rows = _to_excel_preview_rows(items)
    return {
        "columns": ["Posicion", "Titulo", "Precio", "Descuento", "Estado", "Link"],
        "rows": rows,
        "count": len(rows),
        "elapsed_seconds": round(elapsed, 2),
        "limit": limit,
        "pages_fetched": meta.get("pages_fetched", 0),
        "fetched_raw": meta.get("fetched_raw", 0),
        "total_matches": meta.get("total", 0),
        "split_by_price": bool(meta.get("split_by_price")),
        "split_ranges": meta.get("split_ranges", []),
    }


@app.post("/api/categories")
def categories(payload: SearchPayload) -> dict:
    if not payload.query.strip() and not payload.search_url.strip():
        return {"success": True, "categories": []}
    try:
        ml.configure_cookie_header(None, _resolve_cookie_file(payload.cookie_file))
        condition_filter = payload.condition if payload.condition in {"any", "new", "used", "reconditioned"} else "any"
        first_url = ml.build_initial_listing_url(
            payload.query.strip(),
            payload.country,
            not bool(payload.include_international),
            max(0, int(payload.min_price)),
            max(0, int(payload.max_price)),
            max(0, min(100, int(payload.min_discount))),
            bool(payload.sort_price),
            condition_filter,
            search_url=payload.search_url.strip() or None,
        )
        meta = ml.search_metadata_from_url(first_url, payload.country)
        return {"success": True, "categories": ml.categories_from_search_api(meta)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error cargando categorías: {exc}") from exc


def _run_global_job(job_id: str, raw_config: dict) -> None:
    """Run global search in background thread and store result in _JOBS."""
    def progress_callback(source: str, payload: dict) -> None:
        with _JOBS_LOCK:
            job = _JOBS.get(job_id)
            if not job:
                return
            if "items" not in job or job["items"] is None:
                job["items"] = []
            if "runs" not in job or job["runs"] is None:
                job["runs"] = []
            
            source_items = [{"source": source, **item} for item in (payload.get("items") or [])]
            job["items"] = [item for item in job["items"] if item.get("source") != source]
            job["items"].extend(source_items)
            
            job["runs"] = [run for run in job["runs"] if run.get("source") != source]
            job["runs"].append({
                "source": source,
                "ok": payload.get("ok", False),
                "count": len(payload.get("items") or []),
                "output_file": payload.get("output_file"),
                "error": payload.get("error"),
                "warning": payload.get("warning"),
                "elapsed_seconds": payload.get("elapsed_seconds", 0)
            })
            job["total_count"] = len(job["items"])

    try:
        with _JOBS_LOCK:
            if job_id in _JOBS:
                _JOBS[job_id]["items"] = []
                _JOBS[job_id]["runs"] = []
                _JOBS[job_id]["total_count"] = 0

        result = global_search.run_global_search(raw_config, progress_callback=progress_callback)
        with _JOBS_LOCK:
            _JOBS[job_id]["status"] = "done"
            _JOBS[job_id]["result"] = result
            _JOBS[job_id]["items"] = result.get("items", [])
            _JOBS[job_id]["runs"] = result.get("runs", [])
            _JOBS[job_id]["total_count"] = result.get("total_count", 0)
    except Exception as exc:
        with _JOBS_LOCK:
            _JOBS[job_id]["status"] = "error"
            _JOBS[job_id]["error"] = str(exc)
    finally:
        with _JOBS_LOCK:
            _JOBS[job_id]["finished_at"] = time.time()


@app.post("/api/global-search")
def global_search_start(payload: GlobalSearchPayload) -> dict:
    raw = payload.model_dump()
    cfg = global_search.build_config(raw)
    if not cfg["query"] and any(s != "descuentosrata" for s in cfg["sources"]):
        raise HTTPException(status_code=400, detail="Debes indicar una busqueda para las fuentes principales.")

    job_id = uuid.uuid4().hex[:12]
    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "status": "running",
            "query": cfg["query"],
            "sources": cfg["sources"],
            "started_at": time.time(),
            "finished_at": None,
            "result": None,
            "error": None,
            "items": [],
            "runs": [],
            "total_count": 0,
        }
    thread = threading.Thread(target=_run_global_job, args=(job_id, raw), daemon=True)
    thread.start()
    return {"job_id": job_id, "status": "running"}


@app.get("/api/global-search/{job_id}")
def global_search_poll(job_id: str) -> dict:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")

    elapsed = round(time.time() - job["started_at"], 1)

    if job["status"] == "running":
        return {
            "job_id": job_id,
            "status": "running",
            "elapsed_seconds": elapsed,
            "total_count": job.get("total_count", 0),
            "items": job.get("items", []),
            "runs": job.get("runs", []),
        }

    if job["status"] == "error":
        return {"job_id": job_id, "status": "error", "error": job["error"], "elapsed_seconds": elapsed}

    result = job["result"] or {}
    runs = job.get("runs") or result.get("runs") or []
    return {
        "job_id": job_id,
        "status": "done",
        "elapsed_seconds": result.get("elapsed_seconds", elapsed),
        "total_count": job.get("total_count") or result.get("total_count", 0),
        "query": result.get("query", job.get("query", "")),
        "scan_scope": result.get("scan_scope", ""),
        "items": job.get("items") or result.get("items", []),
        "runs": runs,
    }


@app.get("/api/global-categories")
def global_categories(
    query: str = "",
    knasta_knastaday: int = 0,
    knasta_retails: str = "",
    tuganga_mode: str = "all_offers",
) -> dict:
    categories: dict[str, list[dict]] = {
        "pulga": [
            {"id": "", "value": "", "label": "Todas"},
            {"id": "tecnologia", "value": "tecnologia", "label": "Tecnologia"},
            {"id": "moda", "value": "moda", "label": "Moda"},
            {"id": "bebes", "value": "bebes", "label": "Bebe y Ninos"},
            {"id": "entretenimiento", "value": "entretenimiento", "label": "Entretenimiento"},
            {"id": "coleccionismo", "value": "coleccionismo", "label": "Coleccionismo"},
            {"id": "deporte", "value": "deporte", "label": "Deporte"},
            {"id": "bicicletas", "value": "bicicletas", "label": "Bicicletas"},
            {"id": "hogar", "value": "hogar", "label": "Hogar y Jardin"},
            {"id": "electrodomesticos", "value": "electrodomesticos", "label": "Electrodomesticos"},
        ],
        "knasta": [],
        "solotodo": [],
        "travel": [],
        "tuganga": [],
    }
    errors: dict[str, str] = {}

    try:
        import knasta_api

        opts = knasta_api.SearchOptions(
            query=query.strip(),
            knastaday=max(0, int(knasta_knastaday or 0)),
            retails=[r.strip() for r in knasta_retails.split(",") if r.strip()],
        )
        categories["knasta"] = [
            {
                "id": str(cat.get("value") or cat.get("id") or ""),
                "value": str(cat.get("value") or cat.get("id") or ""),
                "label": str(cat.get("label") or cat.get("name") or ""),
                "count": cat.get("count"),
            }
            for cat in knasta_api.categories_for_options(opts, include_counts=True)
        ]
    except Exception as exc:
        errors["knasta"] = str(exc)

    try:
        import solotodo

        categories["solotodo"] = [
            {"id": int(cat.get("id") or 0), "value": int(cat.get("id") or 0), "label": str(cat.get("name") or "")}
            for cat in solotodo.fetch_categories()
        ]
    except Exception as exc:
        errors["solotodo"] = str(exc)

    try:
        import travel

        categories["travel"] = [
            {
                "id": str(cat.get("id") or ""),
                "value": str(cat.get("id") or ""),
                "label": str(cat.get("path") or cat.get("name") or ""),
                "depth": cat.get("depth", 0),
            }
            for cat in travel.fetch_categories()
        ]
    except Exception as exc:
        errors["travel"] = str(exc)

    try:
        import tuganga_api

        tuganga_query = query.strip()
        categories["tuganga"] = [
            {
                "id": str(cat.get("value") or ""),
                "value": str(cat.get("value") or ""),
                "label": str(cat.get("label") or ""),
                "count": cat.get("count"),
            }
            for cat in tuganga_api.categories_for_mode(mode=tuganga_mode, query=tuganga_query)
        ]
    except Exception as exc:
        errors["tuganga"] = str(exc)

    suggested = {}
    try:
        from category_suggest import build_suggestions

        suggested = build_suggestions(query, categories)
    except Exception as exc:
        errors["suggest"] = str(exc)

    return {"success": True, "categories": categories, "suggested": suggested, "errors": errors}


class CookiePayload(BaseModel):
    raw_text: str = Field(default="")


class FacebookCookiePayload(BaseModel):
    profile: str = Field(default="curico")
    raw_text: str = Field(default="")


def _parse_devtools_cookies(raw: str) -> str:
    """Parse cookie text from Chrome DevTools table copy-paste format.
    Supports multiple formats:
      - Tab-separated DevTools table rows (name\tvalue\tdomain...)
      - Multi-space separated rows (tabs pasted as spaces)
      - Simple name=value; pairs (single line or multi-line)
    Returns a cleaned 'name=value; name=value' string.
    """
    raw = raw.strip()
    if not raw:
        return ""

    pairs: list[str] = []
    seen: set[str] = set()

    # Header words to skip (DevTools column headers)
    skip_names = {
        "name", "value", "domain", "path", "expires", "size",
        "httponly", "secure", "samesite", "partition", "priority",
        "max-age", "expires / max-age",
    }

    def _add(name: str, value: str) -> None:
        name = name.strip()
        value = value.strip()
        if not name or name.lower() in skip_names:
            return
        if name.startswith("#"):
            return
        if name not in seen:
            seen.add(name)
            pairs.append(f"{name}={value}")

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue

        # Try tab-separated first (Chrome DevTools native copy)
        parts = line.split("\t")
        if len(parts) >= 2:
            _add(parts[0], parts[1])
            continue

        # Try multi-space separated (tabs pasted as spaces)
        space_parts = re.split(r"\s{2,}", line)
        if len(space_parts) >= 2:
            candidate_name = space_parts[0].strip()
            candidate_value = space_parts[1].strip()
            # Validate it looks like a cookie (name shouldn't have spaces)
            if candidate_name and " " not in candidate_name and candidate_value:
                _add(candidate_name, candidate_value)
                continue

        # Try semicolon-separated name=value pairs (single line)
        if "=" in line:
            for segment in line.split(";"):
                segment = segment.strip()
                if "=" not in segment:
                    continue
                name, _, value = segment.partition("=")
                _add(name, value)

    return "; ".join(pairs)


def _facebook_profile_status(profile_name: str, cookies: dict[str, str]) -> dict:
    valid, message = fb.validate_cookies(cookies)
    return {
        "profile": profile_name,
        "valid": valid,
        "message": message,
        "cookie_count": len(cookies),
        "cookie_names": list(cookies.keys()),
        "has_c_user": bool(cookies.get("c_user")),
        "has_xs": bool(cookies.get("xs")),
    }


@app.post("/api/cookies")
def save_cookies(payload: CookiePayload) -> dict:
    raw = payload.raw_text.strip()
    if not raw:
        raise HTTPException(status_code=400, detail="No se proporcionó texto de cookies.")

    parsed = _parse_devtools_cookies(raw)
    if not parsed:
        raise HTTPException(status_code=400, detail="No se encontraron cookies válidas en el texto proporcionado.")

    cookie_path = ROOT / "cookies.txt"
    cookie_path.write_text(parsed, encoding="utf-8")

    cookie_names = [p.split("=", 1)[0] for p in parsed.split("; ")]
    return {
        "success": True,
        "cookie_count": len(cookie_names),
        "cookie_names": cookie_names,
        "file": str(cookie_path),
    }


@app.get("/api/cookies/status")
def cookies_status() -> dict:
    cookie_path = ROOT / "cookies.txt"
    if not cookie_path.exists():
        return {
            "exists": False,
            "cookie_count": 0,
            "cookie_names": [],
            "file_size": 0,
            "last_modified": None,
            "age_minutes": None,
        }

    content = cookie_path.read_text(encoding="utf-8").strip()
    if not content:
        return {
            "exists": True,
            "cookie_count": 0,
            "cookie_names": [],
            "file_size": 0,
            "last_modified": None,
            "age_minutes": None,
        }

    stat = cookie_path.stat()
    mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    age_minutes = round((datetime.now(tz=timezone.utc) - mtime).total_seconds() / 60, 1)

    names = []
    for segment in content.split(";"):
        segment = segment.strip()
        if "=" in segment:
            name = segment.split("=", 1)[0].strip()
            if name:
                names.append(name)

    essential = ["_csrf", "ssid", "orguseridp", "_d2id"]
    found_essential = [n for n in essential if n in names]

    return {
        "exists": True,
        "cookie_count": len(names),
        "cookie_names": names,
        "essential_found": found_essential,
        "essential_missing": [n for n in essential if n not in names],
        "file_size": stat.st_size,
        "last_modified": mtime.isoformat(),
        "age_minutes": age_minutes,
    }


@app.post("/api/facebook-cookies")
def save_facebook_cookies(payload: FacebookCookiePayload) -> dict:
    raw = payload.raw_text.strip()
    if not raw:
        raise HTTPException(status_code=400, detail="No se proporciono texto de cookies.")

    parsed_header = _parse_devtools_cookies(raw)
    cookies = fb.parse_cookie_string(parsed_header)
    if not cookies:
        raise HTTPException(status_code=400, detail="No se encontraron cookies validas en el texto proporcionado.")

    valid, message = fb.validate_cookies(cookies)
    if not valid:
        raise HTTPException(status_code=400, detail=message)

    profile = "talca" if payload.profile.strip().lower() == "talca" else "curico"
    fb.save_cookies(cookies, profile=profile)
    return {
        "success": True,
        "profile": profile,
        "cookie_count": len(cookies),
        "cookie_names": list(cookies.keys()),
        "message": message,
    }


@app.get("/api/facebook-cookies/status")
def facebook_cookies_status() -> dict:
    profiles = fb.load_cookie_profiles()
    profile_statuses = {
        name: _facebook_profile_status(name, profiles.get(name, {}))
        for name in fb.COOKIE_PROFILE_NAMES
    }
    all_valid = all(status["valid"] for status in profile_statuses.values())
    return {
        "exists": any(status["cookie_count"] > 0 for status in profile_statuses.values()),
        "all_valid": all_valid,
        "profiles": profile_statuses,
        "message": "Perfiles listos." if all_valid else "Faltan cookies validas en uno o mas perfiles.",
    }


@app.get("/api/health")
def healthcheck() -> dict:
    return {
        "status": "ok",
        "frontend_built": WEB_DIST.exists(),
        "cookie_secret_configured": bool(os.getenv("ML_COOKIE", "").strip()),
    }


if WEB_DIST.exists():
    assets_dir = WEB_DIST / "assets"
    index_file = WEB_DIST / "index.html"

    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/")
    def serve_index():
        return FileResponse(index_file)


    @app.get("/{file_path:path}")
    def serve_frontend(file_path: str):
        if file_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")

        candidate = WEB_DIST / file_path
        if candidate.exists() and candidate.is_file():
            return FileResponse(candidate)

        return FileResponse(index_file)

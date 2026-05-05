from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import facebook_marketplace as fbm

ROOT = Path(__file__).resolve().parent
WEB_DIST = ROOT / "web" / "dist"
COUNT_CACHE_TTL_SECONDS = 300
_COUNT_CACHE: dict[str, tuple[float, dict]] = {}
SEARCH_CACHE_TTL_SECONDS = 180
_SEARCH_CACHE: dict[str, tuple[float, fbm.SearchExecutionResult]] = {}
_CACHE_LOCK = threading.Lock()


class SearchPayload(BaseModel):
    query: str = Field(default="")
    marketplace_path: str = Field(default="curico")
    limit: int = Field(default=20)
    scroll_limit: int = Field(default=24)
    min_price: int = Field(default=0)
    max_price: int = Field(default=0)
    word: str = Field(default="")
    include_words: list[str] = Field(default_factory=list)
    exclude_words: list[str] = Field(default_factory=list)
    include_description: bool = Field(default=False)
    storage_state_file: str = Field(default="")
    user_data_dir: str = Field(default="")
    search_url: str = Field(default="")
    location_query: str = Field(default="Curico, Maule, Chile")
    latitude: float | None = Field(default=-34.98749193781055)
    longitude: float | None = Field(default=-71.24675716218236)
    radius_km: int = Field(default=12)
    country_code: str = Field(default="CL")
    show_browser: bool = Field(default=False)
    preview_limit: int = Field(default=40)
    timeout_seconds: int = Field(default=30)


app = FastAPI(title="Facebook Marketplace UI API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5184", "http://127.0.0.1:5184"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _resolve_storage_state(storage_state_file: str) -> str | None:
    raw = storage_state_file.strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / raw
    return str(path)


def _payload_cache_key(payload: SearchPayload) -> str:
    normalized = {
        "query": payload.query.strip(),
        "marketplace_path": payload.marketplace_path.strip(),
        "limit": int(payload.limit),
        "scroll_limit": int(payload.scroll_limit),
        "min_price": int(max(0, payload.min_price)),
        "max_price": int(max(0, payload.max_price)),
        "word": payload.word.strip(),
        "include_words": sorted([str(w).strip() for w in payload.include_words if str(w).strip()]),
        "exclude_words": sorted([str(w).strip() for w in payload.exclude_words if str(w).strip()]),
        "include_description": bool(payload.include_description),
        "storage_state_file": payload.storage_state_file.strip(),
        "user_data_dir": payload.user_data_dir.strip(),
        "search_url": payload.search_url.strip(),
        "location_query": payload.location_query.strip(),
        "latitude": payload.latitude,
        "longitude": payload.longitude,
        "radius_km": int(max(0, payload.radius_km)),
        "country_code": payload.country_code.strip().upper(),
        "show_browser": bool(payload.show_browser),
        "timeout_seconds": int(payload.timeout_seconds),
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
    with _CACHE_LOCK:
        _COUNT_CACHE[key] = (time.time() + COUNT_CACHE_TTL_SECONDS, value)


def _search_cache_get(key: str) -> fbm.SearchExecutionResult | None:
    now = time.time()
    with _CACHE_LOCK:
        entry = _SEARCH_CACHE.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if expires_at < now:
            _SEARCH_CACHE.pop(key, None)
            return None
        return value


def _search_cache_set(key: str, value: fbm.SearchExecutionResult) -> None:
    with _CACHE_LOCK:
        _SEARCH_CACHE[key] = (time.time() + SEARCH_CACHE_TTL_SECONDS, value)


def _should_bypass_cache(payload: SearchPayload) -> bool:
    return bool(payload.show_browser)


def _build_options(payload: SearchPayload, limit: int | None = None) -> fbm.SearchOptions:
    storage_state = _resolve_storage_state(payload.storage_state_file)
    user_data_dir = payload.user_data_dir.strip() or None
    # Prefer storage_state whenever it is present. If the user wants to force a
    # persistent Chrome profile, they can leave storage_state_file empty.
    if storage_state:
        user_data_dir = None

    return fbm.SearchOptions(
        query=payload.query.strip(),
        marketplace_path=payload.marketplace_path.strip() or "curico",
        limit=max(1, int(limit if limit is not None else payload.limit)),
        scroll_limit=max(1, int(payload.scroll_limit)),
        min_price=max(0, int(payload.min_price)),
        max_price=max(0, int(payload.max_price)),
        word=payload.word.strip(),
        include_words=[str(w).strip() for w in payload.include_words if str(w).strip()],
        exclude_words=[str(w).strip() for w in payload.exclude_words if str(w).strip()],
        include_description=bool(payload.include_description),
        storage_state=storage_state,
        user_data_dir=user_data_dir,
        search_url=payload.search_url.strip() or None,
        location_query=payload.location_query.strip(),
        latitude=payload.latitude,
        longitude=payload.longitude,
        radius_km=max(0, int(payload.radius_km)),
        country_code=payload.country_code.strip().upper() or "CL",
        show_browser=bool(payload.show_browser),
        timeout_seconds=max(5, int(payload.timeout_seconds)),
    )


def _run_search_cached(payload: SearchPayload, include_description: bool | None = None) -> fbm.SearchExecutionResult:
    effective_payload = payload.model_copy(
        update={"include_description": payload.include_description if include_description is None else include_description}
    )
    if _should_bypass_cache(effective_payload):
        search_limit = max(int(effective_payload.limit or 1), int(effective_payload.preview_limit or 1))
        return fbm.execute_search(_build_options(effective_payload, limit=search_limit))

    cache_key = f"search:{_payload_cache_key(effective_payload)}"
    cached = _search_cache_get(cache_key)
    if cached is not None:
        return cached

    search_limit = max(int(effective_payload.limit or 1), int(effective_payload.preview_limit or 1))
    result = fbm.execute_search(_build_options(effective_payload, limit=search_limit))
    _search_cache_set(cache_key, result)
    return result


def _to_preview_rows(items: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for idx, item in enumerate(items, start=1):
        rows.append(
            {
                "Posicion": idx,
                "Titulo": str(item.get("title") or ""),
                "Precio": str(item.get("price") or ""),
                "Ubicacion": str(item.get("location") or ""),
                "ZonaBusqueda": str(item.get("search_location") or ""),
                "Publicado": str(item.get("listed") or ""),
                "Descripcion": str(item.get("description") or ""),
                "Link": str(item.get("link") or ""),
            }
        )
    return rows


def _validate_payload(payload: SearchPayload) -> None:
    if not payload.query.strip() and not payload.search_url.strip():
        raise HTTPException(status_code=400, detail="Debes indicar query o search_url.")


@app.post("/api/count-exact")
def count_results_exact(payload: SearchPayload) -> dict:
    _validate_payload(payload)
    cache_key = f"exact:{_payload_cache_key(payload)}"
    if not _should_bypass_cache(payload):
        cached = _cache_get(cache_key)
        if cached is not None:
            return {**cached, "cache_hit": True}

    started = time.perf_counter()
    try:
        result = _run_search_cached(payload, include_description=False)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error ejecutando scraper: {exc}") from exc
    elapsed = time.perf_counter() - started
    response = {
        "count": int(result.total_matches),
        "observed_matches": int(result.observed_matches),
        "elapsed_seconds": round(elapsed, 2),
        "cache_hit": False,
        "source": result.source,
        "filter_breakdown": result.filter_breakdown,
        "applied_filters": {
            "query": payload.query,
            "marketplace_path": payload.marketplace_path,
            "include_words": payload.include_words,
            "exclude_words": payload.exclude_words,
            "min_price": payload.min_price,
            "max_price": payload.max_price,
            "location_query": payload.location_query,
            "radius_km": payload.radius_km,
        },
    }
    if not _should_bypass_cache(payload):
        _cache_set(cache_key, response)
    return response


@app.post("/api/preview")
def preview_results(payload: SearchPayload) -> dict:
    _validate_payload(payload)
    started = time.perf_counter()
    preview_limit = max(1, min(int(payload.preview_limit or payload.limit or 80), 500))
    try:
        result = _run_search_cached(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error en previsualizacion: {exc}") from exc
    elapsed = time.perf_counter() - started
    return {
        "columns": [
            "Posicion",
            "Titulo",
            "Precio",
            "Ubicacion",
            "ZonaBusqueda",
            "Publicado",
            "Descripcion",
            "Link",
        ],
        "rows": _to_preview_rows(result.all_items[:preview_limit]),
        "count": len(result.all_items[:preview_limit]),
        "total_count": int(result.total_matches),
        "observed_matches": int(result.observed_matches),
        "elapsed_seconds": round(elapsed, 2),
        "limit": preview_limit,
        "source": result.source,
        "filter_breakdown": result.filter_breakdown,
    }


@app.post("/api/export")
def export_results(payload: SearchPayload):
    _validate_payload(payload)
    started = time.perf_counter()
    try:
        result = _run_search_cached(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error exportando: {exc}") from exc

    export_path = Path(tempfile.mktemp(prefix="fbm_export_", suffix=".json"))
    export_path.write_text(json.dumps(result.all_items, ensure_ascii=False, indent=2), encoding="utf-8")
    elapsed = time.perf_counter() - started
    filename = f"facebook_marketplace_export_{int(time.time())}.json"
    return FileResponse(
        path=export_path,
        media_type="application/json",
        filename=filename,
        headers={
            "X-Elapsed-Seconds": str(round(elapsed, 2)),
            "X-Total-Matches": str(int(result.total_matches)),
            "X-Observed-Matches": str(int(result.observed_matches)),
            "X-Source": result.source,
            "X-Captured-Raw": str(int(result.filter_breakdown.get("captured_raw", result.observed_matches))),
            "X-After-Text-Price-Filters": str(
                int(result.filter_breakdown.get("after_text_price_filters", result.total_matches))
            ),
        },
    )


@app.get("/api/health")
def healthcheck() -> dict:
    return {
        "status": "ok",
        "frontend_built": WEB_DIST.exists(),
        "playwright_storage_state": bool(os.getenv("FB_MARKETPLACE_STORAGE_STATE", "").strip()),
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

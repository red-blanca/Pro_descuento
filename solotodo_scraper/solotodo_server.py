"""
SoloTodo Export Tool — FastAPI backend.

Run:
    python solotodo_server.py          # production (port 8000)
    uvicorn solotodo_server:app --reload --port 8000  # dev
"""
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

import solotodo as st

ROOT = Path(__file__).resolve().parent
WEB_DIST = ROOT / "web" / "dist"
COUNT_CACHE_TTL = 300
_COUNT_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_LOCK = threading.Lock()


class SearchPayload(BaseModel):
    query: str = Field(default="")
    category_id: int = Field(default=0)
    country_id: int = Field(default=1)
    ordering: str = Field(default="offer_price_usd")
    min_price: float = Field(default=0)
    max_price: float = Field(default=0)
    include_words: list[str] = Field(default_factory=list)
    exclude_words: list[str] = Field(default_factory=list)
    scan_scope: str = Field(default="fast")
    preview_limit: int = Field(default=200)
    max_items: int = Field(default=10000)


app = FastAPI(title="SoloTodo Export API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5188",
        "http://127.0.0.1:5188",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------
def _cache_key(payload: SearchPayload) -> str:
    normalized = {
        "query": payload.query.strip(),
        "category_id": payload.category_id,
        "country_id": payload.country_id,
        "ordering": payload.ordering,
        "min_price": payload.min_price,
        "max_price": payload.max_price,
        "include_words": sorted([w.strip() for w in payload.include_words if w.strip()]),
        "exclude_words": sorted([w.strip() for w in payload.exclude_words if w.strip()]),
        "scan_scope": payload.scan_scope,
    }
    raw = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> dict | None:
    with _CACHE_LOCK:
        entry = _COUNT_CACHE.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if expires_at < time.time():
            _COUNT_CACHE.pop(key, None)
            return None
        return value


def _cache_set(key: str, value: dict) -> None:
    with _CACHE_LOCK:
        _COUNT_CACHE[key] = (time.time() + COUNT_CACHE_TTL, value)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _has_search_input(payload: SearchPayload) -> bool:
    return bool(payload.query.strip() or payload.category_id > 0)


def _collect_items(payload: SearchPayload, limit: int) -> tuple[list[dict], dict]:
    cat_id = payload.category_id if payload.category_id > 0 else None
    fetch_all = payload.scan_scope == "complete"

    items, meta = st.collect_browse_results(
        query=payload.query.strip(),
        category_id=cat_id,
        country_id=payload.country_id,
        ordering=payload.ordering,
        limit=limit,
        fetch_all=fetch_all,
    )

    items = st.apply_filters(
        items,
        min_price=max(0, payload.min_price),
        max_price=max(0, payload.max_price),
        include_words=[w.strip() for w in payload.include_words if w.strip()],
        exclude_words=[w.strip() for w in payload.exclude_words if w.strip()],
    )

    return items[:limit], meta


def _to_preview_rows(items: list[dict]) -> list[dict]:
    rows = []
    for item in items:
        rows.append({
            "Posicion": item.get("position", 0),
            "Nombre": item.get("name", ""),
            "Marca": item.get("brand", ""),
            "Precio Normal": item.get("normal_price", ""),
            "Precio Oferta": item.get("offer_price", ""),
            "Descuento": f"{item['discount_percent']}%" if item.get("discount_percent") else "",
            "Link": item.get("link", ""),
        })
    return rows


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/categories")
@app.post("/api/categories")
def categories():
    try:
        cats = st.fetch_categories()
        return {"success": True, "categories": cats}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error cargando categorías: {exc}")


@app.post("/api/count")
def count_results(payload: SearchPayload):
    if not _has_search_input(payload):
        raise HTTPException(status_code=400, detail="Debes indicar búsqueda o categoría.")

    cache_key = f"count:{_cache_key(payload)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return {**cached, "cache_hit": True}

    started = time.perf_counter()
    try:
        cat_id = payload.category_id if payload.category_id > 0 else None
        computed = st.count_products(
            query=payload.query.strip(),
            category_id=cat_id,
            country_id=payload.country_id,
            ordering=payload.ordering,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error en conteo: {exc}")

    elapsed = time.perf_counter() - started
    response = {
        "count": computed["count"],
        "elapsed_seconds": round(elapsed, 2),
        "cache_hit": False,
        "count_source": computed.get("count_source", "api"),
    }
    _cache_set(cache_key, response)
    return response


@app.post("/api/preview")
def preview_results(payload: SearchPayload):
    if not _has_search_input(payload):
        raise HTTPException(status_code=400, detail="Debes indicar búsqueda o categoría.")

    limit = max(1, min(int(payload.preview_limit or 200), 10000))
    started = time.perf_counter()
    try:
        items, meta = _collect_items(payload, limit)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error en previsualización: {exc}")

    elapsed = time.perf_counter() - started
    rows = _to_preview_rows(items)
    return {
        "columns": ["Posicion", "Nombre", "Marca", "Precio Normal", "Precio Oferta", "Descuento", "Link"],
        "rows": rows,
        "count": len(rows),
        "elapsed_seconds": round(elapsed, 2),
        "limit": limit,
        "pages_fetched": meta.get("pages_fetched", 0),
        "fetched_raw": meta.get("fetched_raw", 0),
        "total_matches": meta.get("total", 0),
    }


@app.post("/api/export")
def export_results(payload: SearchPayload):
    if not _has_search_input(payload):
        raise HTTPException(status_code=400, detail="Debes indicar búsqueda o categoría.")

    limit = max(1, min(int(payload.max_items or 10000), 10000))
    if payload.scan_scope == "complete":
        limit = 10000

    try:
        items, _meta = _collect_items(payload, limit)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error exportando: {exc}")

    export_path = Path(tempfile.mktemp(prefix="st_export_", suffix=".json"))
    export_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    return FileResponse(
        path=export_path,
        media_type="application/json",
        filename=f"solotodo_export_{int(time.time())}.json",
    )


@app.get("/api/health")
def healthcheck():
    return {
        "status": "ok",
        "service": "solotodo",
        "frontend_built": WEB_DIST.exists(),
    }


# ---------------------------------------------------------------------------
# Serve frontend
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run("solotodo_server:app", host="0.0.0.0", port=port, reload=True)

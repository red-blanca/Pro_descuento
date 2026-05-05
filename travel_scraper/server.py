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

import travel


ROOT = Path(__file__).resolve().parent
WEB_DIST = ROOT / "web" / "dist"
CACHE_TTL = 300
_COUNT_CACHE: dict[str, tuple[float, dict]] = {}
_LOCK = threading.Lock()


class SearchPayload(BaseModel):
    query: str = Field(default="")
    category_id: str = Field(default="")
    ordering: str = Field(default="relevance")
    min_price: float = Field(default=0)
    max_price: float = Field(default=0)
    include_words: list[str] = Field(default_factory=list)
    exclude_words: list[str] = Field(default_factory=list)
    scan_scope: str = Field(default="fast")
    preview_limit: int = Field(default=200)
    max_items: int = Field(default=10000)


app = FastAPI(title="Travel Tienda Scraper API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5189",
        "http://127.0.0.1:5189",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _cache_key(payload: SearchPayload) -> str:
    raw = json.dumps(payload.model_dump(), ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> dict | None:
    with _LOCK:
        entry = _COUNT_CACHE.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if expires_at < time.time():
            _COUNT_CACHE.pop(key, None)
            return None
        return value


def _cache_set(key: str, value: dict) -> None:
    with _LOCK:
        _COUNT_CACHE[key] = (time.time() + CACHE_TTL, value)


def _collect(payload: SearchPayload, limit: int) -> tuple[list[dict], dict]:
    fetch_all = payload.scan_scope == "complete"
    items, meta = travel.collect_results(
        query=payload.query.strip(),
        category_id=payload.category_id.strip(),
        ordering=payload.ordering,
        limit=limit,
        fetch_all=fetch_all,
    )
    items = travel.apply_filters(
        items,
        min_price=max(0, payload.min_price),
        max_price=max(0, payload.max_price),
        include_words=[w.strip() for w in payload.include_words if w.strip()],
        exclude_words=[w.strip() for w in payload.exclude_words if w.strip()],
        ordering=payload.ordering,
    )
    return items[:limit], meta


def _rows(items: list[dict]) -> list[dict]:
    return [
        {
            "Posicion": item.get("position", 0),
            "SKU": item.get("id", ""),
            "Nombre": item.get("name", ""),
            "Marca": item.get("brand", ""),
            "Categoria": item.get("category", ""),
            "Precio Normal": item.get("normal_price", ""),
            "Precio Oferta": item.get("offer_price", ""),
            "Descuento": f"{item['discount_percent']}%" if item.get("discount_percent") else "",
            "Link": item.get("link", ""),
        }
        for item in items
    ]


@app.get("/api/categories")
@app.post("/api/categories")
def categories():
    try:
        return {"success": True, "categories": travel.fetch_categories()}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error cargando categorias: {exc}") from exc


@app.post("/api/count")
def count(payload: SearchPayload):
    cache_key = f"count:{_cache_key(payload)}"
    cached = _cache_get(cache_key)
    if cached:
        return {**cached, "cache_hit": True}

    started = time.perf_counter()
    try:
        result = travel.count_products(payload.query.strip(), payload.category_id.strip())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error en conteo: {exc}") from exc

    response = {
        "count": result["count"],
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "cache_hit": False,
        "count_source": result.get("count_source", "api"),
    }
    _cache_set(cache_key, response)
    return response


@app.post("/api/preview")
def preview(payload: SearchPayload):
    limit = max(1, min(int(payload.preview_limit or 200), 10000))
    started = time.perf_counter()
    try:
        items, meta = _collect(payload, limit)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error en previsualizacion: {exc}") from exc

    return {
        "columns": ["Posicion", "SKU", "Nombre", "Marca", "Categoria", "Precio Normal", "Precio Oferta", "Descuento", "Link"],
        "rows": _rows(items),
        "count": len(items),
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "pages_fetched": meta.get("pages_fetched", 0),
        "fetched_raw": meta.get("fetched_raw", 0),
        "total_matches": meta.get("total", 0),
    }


@app.post("/api/export")
def export(payload: SearchPayload):
    limit = max(1, min(int(payload.max_items or 10000), 10000))
    if payload.scan_scope == "complete":
        limit = 10000

    try:
        items, _meta = _collect(payload, limit)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error exportando: {exc}") from exc

    path = Path(tempfile.mktemp(prefix="travel_export_", suffix=".json"))
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    return FileResponse(
        path=path,
        media_type="application/json",
        filename=f"travel_export_{int(time.time())}.json",
    )


@app.get("/api/health")
def healthcheck():
    return {"status": "ok", "service": "travel", "frontend_built": WEB_DIST.exists()}


if WEB_DIST.exists():
    assets = WEB_DIST / "assets"
    index = WEB_DIST / "index.html"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/")
    def serve_index():
        return FileResponse(index)

    @app.get("/{file_path:path}")
    def serve_frontend(file_path: str):
        if file_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = WEB_DIST / file_path
        if candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=int(os.getenv("PORT", "8050")), reload=True)

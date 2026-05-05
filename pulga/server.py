from __future__ import annotations

import os
import hashlib
import json
import tempfile
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import pulga as scraper

ROOT = Path(__file__).resolve().parent
WEB_DIST = ROOT / "web" / "dist"
COUNT_CACHE_TTL_SECONDS = 300
_COUNT_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_LOCK = threading.Lock()


class SearchPayload(BaseModel):
    query: str = Field(default="")
    category: str = Field(default="")
    all_results: bool = Field(default=True)
    max_pages: int = Field(default=0)
    min_price: int = Field(default=0)
    max_price: int = Field(default=0)
    word: str = Field(default="")
    include_words: list[str] = Field(default_factory=list)
    exclude_words: list[str] = Field(default_factory=list)
    condition: str = Field(default="any")
    sort_price: bool = Field(default=True)
    city: str = Field(default="")
    preview_limit: int = Field(default=200)


app = FastAPI(title="Pulga.cl Scraper API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _payload_cache_key(payload: SearchPayload) -> str:
    normalized = {
        "query": payload.query.strip(),
        "category": payload.category.strip(),
        "all_results": bool(payload.all_results),
        "max_pages": int(payload.max_pages),
        "min_price": int(max(0, payload.min_price)),
        "max_price": int(max(0, payload.max_price)),
        "word": payload.word.strip(),
        "include_words": sorted([str(w).strip() for w in payload.include_words if str(w).strip()]),
        "exclude_words": sorted([str(w).strip() for w in payload.exclude_words if str(w).strip()]),
        "condition": payload.condition,
        "sort_price": bool(payload.sort_price),
        "city": payload.city.strip(),
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


def _run_scraper(payload: SearchPayload) -> tuple[list[dict], int]:
    """Run the scraper with the given payload parameters."""
    items, total = scraper.collect_results(
        query=payload.query.strip(),
        category=payload.category.strip() or None,
        limit=max(1, payload.preview_limit),
        fetch_all=bool(payload.all_results),
        max_pages=int(payload.max_pages),
        quiet=True,
    )

    items = scraper.apply_filters(
        items,
        min_price=max(0, int(payload.min_price)),
        max_price=max(0, int(payload.max_price)),
        condition_filter=payload.condition,
        word=payload.word.strip(),
        include_words=[str(w).strip() for w in payload.include_words if str(w).strip()],
        exclude_words=[str(w).strip() for w in payload.exclude_words if str(w).strip()],
        city_filter=payload.city.strip(),
    )

    if payload.sort_price:
        items = scraper.sort_items_by_price(items)
    else:
        for idx, item in enumerate(items, start=1):
            item["position"] = idx

    return items, total


def _applied_filters(payload: SearchPayload) -> dict:
    return {
        "query": payload.query,
        "category": payload.category,
        "min_price": payload.min_price,
        "max_price": payload.max_price,
        "include_words": payload.include_words,
        "exclude_words": payload.exclude_words,
        "condition": payload.condition,
        "city": payload.city,
    }


def _to_preview_rows(items: list[dict]) -> list[dict]:
    condition_map = {"new": "Nuevo", "used": "Usado"}
    rows: list[dict] = []
    for idx, item in enumerate(items, start=1):
        cond = condition_map.get(str(item.get("condition") or "").lower(), "N/D")
        rows.append({
            "Posicion": idx,
            "Titulo": str(item.get("title") or ""),
            "Precio": item.get("price_display") or "",
            "Condicion": cond,
            "Ciudad": str(item.get("city") or ""),
            "Vendedor": str(item.get("seller") or ""),
            "Link": str(item.get("link") or ""),
        })
    return rows


def _has_client_side_filters(payload: SearchPayload) -> bool:
    """Check if the payload requires client-side filtering (price, words, city, condition)."""
    if payload.min_price > 0 or payload.max_price > 0:
        return True
    if payload.word.strip():
        return True
    if any(str(w).strip() for w in payload.include_words):
        return True
    if any(str(w).strip() for w in payload.exclude_words):
        return True
    if payload.city.strip():
        return True
    if payload.condition not in ("any", ""):
        return True
    return False


@app.post("/api/count")
def count_results(payload: SearchPayload) -> dict:
    if not payload.query.strip() and not payload.category.strip():
        raise HTTPException(status_code=400, detail="Debes indicar query o categoria.")

    cache_key = _payload_cache_key(payload)
    cached = _cache_get(cache_key)
    if cached is not None:
        return {**cached, "cache_hit": True}

    started = time.perf_counter()

    # Fast path: if no client-side filters, just use the API total (1 request)
    if not _has_client_side_filters(payload):
        try:
            total, _pages = scraper.quick_count(
                query=payload.query.strip(),
                category=payload.category.strip() or None,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Error en scraper: {exc}") from exc
        elapsed = time.perf_counter() - started

        response = {
            "count": total,
            "total_available": total,
            "elapsed_seconds": round(elapsed, 2),
            "cache_hit": False,
            "fast_count": True,
            "applied_filters": _applied_filters(payload),
        }
        _cache_set(cache_key, response)
        return response

    # Slow path: need to fetch all items and filter client-side
    try:
        items, total = _run_scraper(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error en scraper: {exc}") from exc
    elapsed = time.perf_counter() - started

    response = {
        "count": len(items),
        "total_available": total,
        "elapsed_seconds": round(elapsed, 2),
        "cache_hit": False,
        "fast_count": False,
        "applied_filters": _applied_filters(payload),
    }
    _cache_set(cache_key, response)
    return response


@app.post("/api/preview")
def preview_results(payload: SearchPayload) -> dict:
    if not payload.query.strip() and not payload.category.strip():
        raise HTTPException(status_code=400, detail="Debes indicar query o categoria.")

    started = time.perf_counter()
    try:
        items, total = _run_scraper(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error en scraper: {exc}") from exc
    elapsed = time.perf_counter() - started

    rows = _to_preview_rows(items)
    return {
        "columns": ["Posicion", "Titulo", "Precio", "Condicion", "Ciudad", "Vendedor", "Link"],
        "rows": rows,
        "count": len(rows),
        "total_available": total,
        "elapsed_seconds": round(elapsed, 2),
    }


@app.post("/api/export")
def export_results(payload: SearchPayload):
    if not payload.query.strip() and not payload.category.strip():
        raise HTTPException(status_code=400, detail="Debes indicar query o categoria.")

    started = time.perf_counter()
    try:
        items, total = _run_scraper(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error en scraper: {exc}") from exc

    if not items:
        raise HTTPException(status_code=400, detail="No se encontraron resultados.")

    export_path = Path(tempfile.mktemp(prefix="pulga_export_", suffix=".json"))
    export_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    query_part = payload.query.strip() or payload.category.strip() or "pulga"
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in query_part)[:30]
    filename = f"pulga_{safe_name}_{len(items)}items.json"

    return FileResponse(
        path=export_path,
        media_type="application/json",
        filename=filename,
    )


@app.get("/api/categories")
def list_categories() -> dict:
    return {
        "categories": [
            {"key": k, "slug": v, "label": k.replace("_", " ").capitalize()}
            for k, v in scraper.CATEGORY_SLUGS.items()
        ]
    }


@app.get("/api/health")
def healthcheck() -> dict:
    return {
        "status": "ok",
        "service": "pulga-scraper",
        "frontend_built": WEB_DIST.exists(),
    }


# ── Serve frontend SPA ──────────────────────────────────────────────────

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

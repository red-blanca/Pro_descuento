from __future__ import annotations

import os
import hashlib
import json
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import mercadolibre as ml

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "mercadolibre.py"
WEB_DIST = ROOT / "web" / "dist"
COUNT_CACHE_TTL_SECONDS = 300
_COUNT_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_LOCK = threading.Lock()


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
        items = [item for item in items if item.get("condition") == condition_filter]
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

    with tempfile.NamedTemporaryFile(prefix="ml_export_", suffix=".xlsx", delete=False) as tmp:
        export_path = Path(tmp.name)
    limit = max(1, min(int(payload.preview_limit or 2000), 10000))
    if payload.scan_scope == "complete" or payload.all_results:
        limit = 10000
    try:
        items, _meta = _collect_preview_items(payload, limit)
        export_path.write_bytes(ml.build_xlsx_bytes(items))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error exportando: {exc}") from exc

    return FileResponse(
        path=export_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=export_path.name,
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

"""
FastAPI server for Facebook Marketplace HTTP scraper.
No Playwright needed — uses direct HTTP requests with cookies.
"""
from __future__ import annotations

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

import facebook_api as fb

ROOT = Path(__file__).resolve().parent
WEB_DIST = ROOT / "web" / "dist"
SEARCH_CACHE_TTL = 180
_SEARCH_CACHE: dict[str, tuple[float, fb.SearchResult]] = {}
_CACHE_LOCK = threading.Lock()


class SearchPayload(BaseModel):
    query: str = Field(default="")
    marketplace_path: str = Field(default="curico")
    limit: int = Field(default=40)
    max_pages: int = Field(default=3)
    min_price: int = Field(default=0)
    max_price: int = Field(default=0)
    word: str = Field(default="")
    include_words: list[str] = Field(default_factory=list)
    exclude_words: list[str] = Field(default_factory=list)
    location_query: str = Field(default="Curico, Maule, Chile")
    latitude: float | None = Field(default=-34.98749193781055)
    longitude: float | None = Field(default=-71.24675716218236)
    radius_km: int = Field(default=12)
    include_talca: bool = Field(default=False)
    country_code: str = Field(default="CL")
    preview_limit: int = Field(default=40)


class CookiePayload(BaseModel):
    profile: str = Field(default="curico")
    cookie_string: str = Field(default="")
    cookies_dict: dict[str, str] = Field(default_factory=dict)


app = FastAPI(title="Facebook Marketplace API (HTTP)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def _cache_key(payload: SearchPayload) -> str:
    norm = json.dumps({
        "query": payload.query.strip(),
        "marketplace_path": payload.marketplace_path.strip(),
        "limit": int(payload.limit),
        "max_pages": int(max(0, payload.max_pages)),
        "min_price": int(max(0, payload.min_price)),
        "max_price": int(max(0, payload.max_price)),
        "word": payload.word.strip(),
        "include_words": sorted(w.strip() for w in payload.include_words if w.strip()),
        "exclude_words": sorted(w.strip() for w in payload.exclude_words if w.strip()),
        "location_query": payload.location_query.strip(),
        "latitude": payload.latitude,
        "longitude": payload.longitude,
        "radius_km": int(max(0, payload.radius_km)),
        "include_talca": bool(payload.include_talca),
        "country_code": payload.country_code.strip().upper(),
    }, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(norm.encode()).hexdigest()


def _cache_get(key: str) -> fb.SearchResult | None:
    with _CACHE_LOCK:
        entry = _SEARCH_CACHE.get(key)
        if not entry:
            return None
        if entry[0] < time.time():
            _SEARCH_CACHE.pop(key, None)
            return None
        return entry[1]


def _cache_set(key: str, value: fb.SearchResult) -> None:
    with _CACHE_LOCK:
        _SEARCH_CACHE[key] = (time.time() + SEARCH_CACHE_TTL, value)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_options(p: SearchPayload) -> fb.SearchOptions:
    return fb.SearchOptions(
        query=p.query.strip(),
        marketplace_path=p.marketplace_path.strip() or "curico",
        limit=max(1, int(p.limit)),
        max_pages=max(0, min(int(p.max_pages), 5)),
        min_price=max(0, int(p.min_price)),
        max_price=max(0, int(p.max_price)),
        word=p.word.strip(),
        include_words=[w.strip() for w in p.include_words if w.strip()],
        exclude_words=[w.strip() for w in p.exclude_words if w.strip()],
        location_query=p.location_query.strip(),
        latitude=p.latitude,
        longitude=p.longitude,
        radius_km=max(0, int(p.radius_km)),
        include_talca=bool(p.include_talca),
        country_code=p.country_code.strip().upper() or "CL",
    )


def _run_search(payload: SearchPayload, min_limit: int | None = None) -> fb.SearchResult:
    if min_limit is not None and int(min_limit) > int(payload.limit):
        payload = payload.model_copy(update={"limit": int(min_limit)})

    key = _cache_key(payload)
    cached = _cache_get(key)
    if cached:
        return cached

    cookie_profiles = fb.load_cookie_profiles()
    has_valid_profile = any(
        fb.validate_cookies(cookie_profiles.get(name, {}))[0]
        for name in fb.COOKIE_PROFILE_NAMES
    )
    if not has_valid_profile:
        raise HTTPException(status_code=400, detail="No hay perfiles de cookies válidos configurados.")

    opts = _build_options(payload)
    result = fb.execute_search(opts, cookie_profiles)
    _cache_set(key, result)
    return result


def _to_preview_rows(items: list[dict]) -> list[dict]:
    return [
        {
            "Posicion": idx,
            "Titulo": str(it.get("title") or ""),
            "Precio": str(it.get("price") or ""),
            "Ubicacion": str(it.get("location") or ""),
            "OrigenBusqueda": str(it.get("marketplace_path_used") or ""),
            "ZonaBusqueda": str(it.get("search_location") or ""),
            "Publicado": str(it.get("listed") or ""),
            "Descripcion": str(it.get("description") or ""),
            "Link": str(it.get("link") or ""),
            "Imagen": str(it.get("image") or ""),
        }
        for idx, it in enumerate(items, start=1)
    ]


# ---------------------------------------------------------------------------
# Cookie endpoints
# ---------------------------------------------------------------------------

@app.get("/api/cookies/status")
def cookies_status():
    profiles = fb.load_cookie_profiles()
    statuses: dict[str, dict[str, object]] = {}
    all_valid = True
    any_valid = False
    for profile_name in fb.COOKIE_PROFILE_NAMES:
        cookies = profiles.get(profile_name, {})
        valid, msg = fb.validate_cookies(cookies)
        if valid:
            any_valid = True
        else:
            all_valid = False
        statuses[profile_name] = {
            "valid": valid,
            "message": msg,
            "keys": list(cookies.keys()),
            "has_c_user": bool(cookies.get("c_user")),
            "has_xs": bool(cookies.get("xs")),
        }
    return {
        "valid": all_valid,
        "any_valid": any_valid,
        "message": "Perfiles listos." if all_valid else "Faltan cookies en uno o más perfiles.",
        "profiles": statuses,
    }


@app.post("/api/cookies")
def save_cookies(payload: CookiePayload):
    profile_name = fb._normalize_profile_name(payload.profile)
    cookies: dict[str, str] = {}

    if payload.cookie_string.strip():
        cookies = fb.parse_cookie_string(payload.cookie_string)
    elif payload.cookies_dict:
        cookies = {k: str(v) for k, v in payload.cookies_dict.items() if v}

    if not cookies:
        raise HTTPException(status_code=400, detail="No se proporcionaron cookies.")

    valid, msg = fb.validate_cookies(cookies)
    if not valid:
        raise HTTPException(status_code=400, detail=msg)

    fb.save_cookies(cookies, profile=profile_name)
    # Clear search cache when cookies change
    with _CACHE_LOCK:
        _SEARCH_CACHE.clear()

    return {"status": "ok", "profile": profile_name, "keys": list(cookies.keys()), "message": msg}


@app.delete("/api/cookies")
def delete_cookies(profile: str = "all"):
    cleaned = str(profile or "").strip().lower()
    if cleaned == "all":
        if fb.COOKIE_PROFILES_FILE.exists():
            fb.COOKIE_PROFILES_FILE.unlink()
        if fb.COOKIES_FILE.exists():
            fb.COOKIES_FILE.unlink()
        if fb.LEGACY_TALCA_COOKIES_FILE.exists():
            fb.LEGACY_TALCA_COOKIES_FILE.unlink()
    else:
        profile_name = fb._normalize_profile_name(profile)
        profiles = fb.load_cookie_profiles()
        profiles[profile_name] = {}
        fb.save_cookie_profiles(profiles)
    with _CACHE_LOCK:
        _SEARCH_CACHE.clear()
    if cleaned == "all":
        return {"status": "ok", "message": "Cookies eliminadas (todos los perfiles)."}
    return {"status": "ok", "message": f"Cookies eliminadas para perfil '{profile_name}'."}


# ---------------------------------------------------------------------------
# Search endpoints
# ---------------------------------------------------------------------------

def _validate_payload(p: SearchPayload) -> None:
    if not p.query.strip():
        raise HTTPException(status_code=400, detail="Debes indicar una búsqueda.")


@app.post("/api/count-exact")
def count_results(payload: SearchPayload):
    _validate_payload(payload)
    started = time.perf_counter()
    try:
        result = _run_search(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error: {exc}") from exc
    elapsed = time.perf_counter() - started
    return {
        "count": result.total_matches,
        "captured_raw": result.captured_raw,
        "elapsed_seconds": round(elapsed, 2),
        "filter_breakdown": result.filter_breakdown,
    }


@app.post("/api/preview")
def preview_results(payload: SearchPayload):
    _validate_payload(payload)
    started = time.perf_counter()
    limit = max(1, min(int(payload.preview_limit or 40), 500))
    try:
        result = _run_search(payload, min_limit=limit)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error: {exc}") from exc
    elapsed = time.perf_counter() - started
    sliced = result.all_items[:limit]
    return {
        "columns": ["Posicion", "Titulo", "Precio", "Ubicacion", "OrigenBusqueda", "ZonaBusqueda", "Publicado", "Descripcion", "Link", "Imagen"],
        "rows": _to_preview_rows(sliced),
        "count": len(sliced),
        "total_count": result.total_matches,
        "captured_raw": result.captured_raw,
        "elapsed_seconds": round(elapsed, 2),
        "filter_breakdown": result.filter_breakdown,
    }


@app.post("/api/export")
def export_results(payload: SearchPayload):
    _validate_payload(payload)
    try:
        result = _run_search(payload, min_limit=max(int(payload.limit or 1), int(payload.preview_limit or 1)))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error: {exc}") from exc

    with tempfile.NamedTemporaryFile(prefix="fbm_", suffix=".xlsx", delete=False) as tmp:
        export_path = Path(tmp.name)
    fb.export_xlsx(result.all_items, query=payload.query.strip() or "marketplace", output_path=str(export_path))
    return FileResponse(
        path=export_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"facebook_marketplace_{int(time.time())}.xlsx",
        headers={
            "X-Total-Matches": str(result.total_matches),
            "X-Captured-Raw": str(result.captured_raw),
        },
    )


@app.get("/api/health")
def healthcheck():
    profiles = fb.load_cookie_profiles()
    valid = all(
        fb.validate_cookies(profiles.get(name, {}))[0]
        for name in fb.COOKIE_PROFILE_NAMES
    )
    return {"status": "ok", "cookies_valid": valid, "frontend_built": WEB_DIST.exists()}


# ---------------------------------------------------------------------------
# Static frontend
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

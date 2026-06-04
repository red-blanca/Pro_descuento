from __future__ import annotations

import os
import re
import sys
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
WEB_DIST = ROOT / "web" / "dist"

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

from pydantic import BaseModel, Field
import global_search
import facebook_api as fb

# Async job store for long-running global searches
_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


_JOB_TTL_SECONDS = max(60, _env_int("GLOBAL_JOB_TTL_SECONDS", 900))
_MAX_FINISHED_JOBS = max(1, _env_int("GLOBAL_MAX_FINISHED_JOBS", 3))
_MAX_CONCURRENT_SEARCHES = max(1, _env_int("GLOBAL_MAX_CONCURRENT_SEARCHES", 1))


def _prune_jobs_locked(now: float | None = None) -> None:
    """Drop old finished jobs so large result sets do not live forever in RAM."""
    now = now or time.time()
    expired = [
        job_id
        for job_id, job in _JOBS.items()
        if job.get("status") != "running"
        and job.get("finished_at")
        and now - float(job.get("finished_at") or now) > _JOB_TTL_SECONDS
    ]
    for job_id in expired:
        _JOBS.pop(job_id, None)

    finished = [
        (float(job.get("finished_at") or 0), job_id)
        for job_id, job in _JOBS.items()
        if job.get("status") != "running"
    ]
    for _finished_at, job_id in sorted(finished, reverse=True)[_MAX_FINISHED_JOBS:]:
        _JOBS.pop(job_id, None)


def _running_jobs_locked() -> int:
    return sum(1 for job in _JOBS.values() if job.get("status") == "running")


def _job_result_for_storage(result: dict) -> dict:
    """Keep only the fields needed by the API response; by_source duplicates items."""
    return {
        "created_at": result.get("created_at"),
        "query": result.get("query", ""),
        "scan_scope": result.get("scan_scope", ""),
        "output_dir": result.get("output_dir"),
        "all_results_file": result.get("all_results_file"),
        "total_count": result.get("total_count", 0),
        "elapsed_seconds": result.get("elapsed_seconds", 0),
        "runs": result.get("runs", []),
        "items": result.get("items", []),
    }


class GlobalSearchPayload(BaseModel):
    query: str = Field(default="")
    sources: list[str] = Field(default_factory=lambda: global_search.DEFAULT_SOURCES.copy())
    scan_scope: str = Field(default="complete")
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
    knasta_category: str = Field(default="")
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
    pcfactory_word: str = Field(default="")
    descuentosrata_all: bool = Field(default=True)
    descuentosrata_limit: int = Field(default=10000)
    strict_mode: bool = Field(default=False)
    smart_filter: bool = Field(default=True)


app = FastAPI(title="Pro Descuento API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)





def _run_global_job(job_id: str, raw_config: dict) -> None:
    """Run global search in background thread and store result in _JOBS."""
    def progress_callback(source: str, payload: dict) -> None:
        with _JOBS_LOCK:
            job = _JOBS.get(job_id)
            if not job:
                return
            if "runs" not in job or job["runs"] is None:
                job["runs"] = []

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
            job["total_count"] = sum(int(run.get("count") or 0) for run in job["runs"])

    try:
        with _JOBS_LOCK:
            if job_id in _JOBS:
                _JOBS[job_id]["runs"] = []
                _JOBS[job_id]["total_count"] = 0

        result = global_search.run_global_search(
            raw_config,
            progress_callback=progress_callback,
            include_by_source=False,
        )
        stored_result = _job_result_for_storage(result)
        with _JOBS_LOCK:
            _JOBS[job_id]["status"] = "done"
            _JOBS[job_id]["result"] = stored_result
            _JOBS[job_id]["runs"] = stored_result.get("runs", [])
            _JOBS[job_id]["total_count"] = stored_result.get("total_count", 0)
    except Exception as exc:
        with _JOBS_LOCK:
            _JOBS[job_id]["status"] = "error"
            _JOBS[job_id]["error"] = str(exc)
    finally:
        with _JOBS_LOCK:
            _JOBS[job_id]["finished_at"] = time.time()
            _prune_jobs_locked()


@app.post("/api/global-search")
def global_search_start(payload: GlobalSearchPayload) -> dict:
    raw = payload.model_dump()
    cfg = global_search.build_config(raw)
    has_category = any([
        cfg.get("pulga_category"),
        cfg.get("knasta_category"),
        cfg.get("solotodo_category_id"),
        cfg.get("travel_category_id"),
        cfg.get("tuganga_categories"),
    ])
    if not cfg["query"] and not has_category and any(s != "descuentosrata" for s in cfg["sources"]):
        raise HTTPException(status_code=400, detail="Debes indicar una búsqueda o seleccionar una categoría.")

    job_id = uuid.uuid4().hex[:12]
    with _JOBS_LOCK:
        _prune_jobs_locked()
        if _running_jobs_locked() >= _MAX_CONCURRENT_SEARCHES:
            raise HTTPException(
                status_code=409,
                detail="Ya hay una busqueda global en curso. Espera que termine antes de iniciar otra.",
            )
        _JOBS[job_id] = {
            "status": "running",
            "query": cfg["query"],
            "sources": cfg["sources"],
            "started_at": time.time(),
            "finished_at": None,
            "result": None,
            "error": None,
            "runs": [],
            "total_count": 0,
        }
    thread = threading.Thread(target=_run_global_job, args=(job_id, raw), daemon=True)
    thread.start()
    return {"job_id": job_id, "status": "running"}


@app.get("/api/global-search/{job_id}")
def global_search_poll(job_id: str) -> dict:
    with _JOBS_LOCK:
        _prune_jobs_locked()
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
            "items": [],
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
        "items": result.get("items", []),
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
        raise HTTPException(status_code=400, detail="No se proporciono texto de cookies.")

    parsed = _parse_devtools_cookies(raw)
    if not parsed:
        raise HTTPException(status_code=400, detail="No se encontraron cookies validas en el texto proporcionado.")

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

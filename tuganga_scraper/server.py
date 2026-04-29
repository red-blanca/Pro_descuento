from __future__ import annotations

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import tuganga_api as tuganga


app = FastAPI(title="TuGanga Scraper API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchPayload(BaseModel):
    query: str = ""
    mode: str = "search"
    stores: list[str] = Field(default_factory=list)
    category: str = ""
    min_discount: int = 0
    min_price: int = 0
    max_price: int = 0
    only_available: bool = False
    sort: str = ""
    limit: int = 80
    max_pages: int = 100
    scan_scope: str = "fast"


@app.post("/api/search")
def search_tuganga(payload: SearchPayload):
    opts = tuganga.SearchOptions(
        query=payload.query.strip(),
        mode=payload.mode.strip() or "search",
        stores=[store.strip() for store in payload.stores if store.strip()],
        category=payload.category.strip(),
        min_discount=max(0, min(100, int(payload.min_discount or 0))),
        min_price=max(0, int(payload.min_price or 0)),
        max_price=max(0, int(payload.max_price or 0)),
        only_available=bool(payload.only_available),
        sort=payload.sort.strip(),
        limit=max(1, int(payload.limit or 80)),
        max_pages=max(1, min(500, int(payload.max_pages or 100))),
        scan_scope=payload.scan_scope.strip() if payload.scan_scope.strip() in {"fast", "complete"} else "fast",
    )
    if opts.mode == "search" and not opts.query:
        raise HTTPException(status_code=400, detail="Debes indicar una busqueda o cambiar el modo.")

    try:
        result = tuganga.execute_search(opts)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "success": True,
        "items": result.items,
        "total_matches": result.total_matches,
        "search_url": result.search_url,
        "mode": result.mode,
        "pages_fetched": result.pages_fetched,
        "fetched_raw": result.fetched_raw,
    }


@app.get("/api/categories")
def categories(mode: str = "all_offers", query: str = ""):
    try:
        return {
            "success": True,
            "mode": mode,
            "categories": tuganga.categories_for_mode(mode=mode, query=query.strip()),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/health")
def healthcheck():
    return {"status": "ok", "service": "tuganga-scraper"}


if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8030, reload=True)

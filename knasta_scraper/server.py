import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import knasta_api as knasta

app = FastAPI(title="Knasta Scraper API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class SearchPayload(BaseModel):
    query: str = ""
    retails: list[str] = Field(default_factory=list)
    knastaday: int = 0
    category: str = ""
    limit: int = 40
    max_pages: int = 100
    scan_scope: str = "fast"

@app.post("/api/search")
def search_knasta(payload: SearchPayload):
    opts = knasta.SearchOptions(
        query=payload.query.strip(),
        retails=[r.strip() for r in payload.retails if r.strip()],
        knastaday=payload.knastaday,
        category=payload.category.strip(),
        limit=max(1, payload.limit),
        max_pages=max(1, min(500, int(payload.max_pages or 100))),
        scan_scope=payload.scan_scope.strip() if payload.scan_scope.strip() in {"fast", "complete"} else "fast",
    )
    
    try:
        result = knasta.execute_search(opts)
        return {
            "success": True,
            "items": result.items,
            "total_matches": result.total_matches,
            "search_url": result.search_url,
            "pages_fetched": result.pages_fetched,
            "fetched_raw": result.fetched_raw,
            "total_pages": result.total_pages,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/categories")
def categories(query: str = "", knastaday: int = 0, retails: str = "", include_counts: bool = True):
    opts = knasta.SearchOptions(
        query=query.strip(),
        retails=[r.strip() for r in retails.split(",") if r.strip()],
        knastaday=max(0, int(knastaday or 0)),
    )
    try:
        return {
            "success": True,
            "categories": knasta.categories_for_options(opts, include_counts=include_counts),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/retails")
def retails(query: str = "", knastaday: int = 0, category: str = ""):
    opts = knasta.SearchOptions(
        query=query.strip(),
        knastaday=max(0, int(knastaday or 0)),
        category=category.strip(),
    )
    try:
        return {
            "success": True,
            "retails": knasta.retails_for_options(opts),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
def healthcheck():
    return {"status": "ok", "service": "knasta-scraper"}

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8020, reload=True)

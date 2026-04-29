import time
import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from pathlib import Path
import descuentosrata_api as api

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"

app = FastAPI(title="DescuentosRata API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SearchPayload(BaseModel):
    query: str = Field(default="")
    min_price: int = Field(default=0)
    max_price: int = Field(default=0)
    limit: int = Field(default=100)

@app.post("/api/preview")
def preview_results(payload: SearchPayload):
    started = time.perf_counter()
    try:
        opts = api.SearchOptions(
            query=payload.query,
            min_price=payload.min_price,
            max_price=payload.max_price,
            limit=payload.limit
        )
        result = api.execute_search(opts)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
        
    elapsed = time.perf_counter() - started
    
    rows = []
    for idx, item in enumerate(result.items, start=1):
        rows.append({
            "Posicion": idx,
            "Tienda": item["store"],
            "Titulo": item["title"],
            "Precio": item["formatted_price"],
            "Descuento": f"{item['discount_percentage']}%" if item["discount_percentage"] > 0 else "",
            "Link": item["link"]
        })
        
    return {
        "columns": ["Posicion", "Tienda", "Titulo", "Precio", "Descuento", "Link"],
        "rows": rows,
        "items": result.items, # Datos completos para la UI premium
        "count": len(rows),
        "total_matches": result.total_matches,
        "elapsed_seconds": round(elapsed, 2),
        "search_url": result.search_url
    }

@app.post("/api/export")
def export_results(payload: SearchPayload):
    try:
        opts = api.SearchOptions(
            query=payload.query,
            min_price=payload.min_price,
            max_price=payload.max_price,
            limit=payload.limit
        )
        result = api.execute_search(opts)
        xlsx_content = api.build_xlsx_bytes(result.items)
        
        # Generar nombre de archivo seguro
        safe_query = re.sub(r"[^a-zA-Z0-9_-]+", "_", payload.query)[:40].strip("_") or "ofertas"
        filename = f"descuentos_rata_{safe_query}.xlsx"
        
        # Guardar temporalmente para FileResponse
        temp_path = Path(f"/tmp/{filename}")
        temp_path.write_bytes(xlsx_content)
        
        return FileResponse(
            path=temp_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=filename
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/")
def serve_index():
    return FileResponse(WEB_DIR / "index.html")

@app.get("/api/health")
def health():
    return {"status": "ok", "source": "descuentosrata"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

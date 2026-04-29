# Travel Tienda Scraper

Scraper/exportador para `https://tienda.travel.cl/`.

Usa endpoints publicos de Oracle Commerce:

- `GET /ccstore/v1/search` para busqueda general y listados grandes.
- `GET /ccstore/v1/products` para categorias.

## Ejecutar

```bash
cd travel_scraper
../.venv/bin/python -m pip install -r requirements.txt
cd web && npm install && cd ..
../.venv/bin/python run_dev.py
```

URLs:

- Frontend: `http://127.0.0.1:5189`
- API: `http://127.0.0.1:8050`

Tambien desde la raiz:

```bash
.venv/bin/python run_all.py travel
```

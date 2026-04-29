# SoloTodo Scraper

Herramienta de Pro Descuento para consultar la API publica de SoloTodo, previsualizar resultados y exportar listas grandes a Excel.

## Ejecutar

```bash
cd solotodo_scraper
python3 -m pip install -r requirements.txt
cd web && npm install && cd ..
python3 run_dev.py
```

URLs por defecto:

- Frontend: `http://127.0.0.1:5188`
- API: `http://127.0.0.1:8001`

Tambien se puede levantar desde la raiz:

```bash
python3 run_all.py solotodo
```

## Endpoints

- `GET|POST /api/categories`: categorias de SoloTodo.
- `POST /api/count`: conteo rapido desde la API.
- `POST /api/preview`: resultados paginados para revisar en tabla.
- `POST /api/export`: Excel con precio normal, precio oferta, descuento y link.

La extraccion usa `https://publicapi.solotodo.com/products/browse/`, con paginacion paralela para listas grandes.

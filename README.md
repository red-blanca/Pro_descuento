# MercadoLibre Scraper (CLI)

Script de consola para buscar productos en Mercado Libre y exportar resultados a Excel.

## Modo visual (React + API)

Ahora el proyecto incluye una interfaz visual para:

- Aplicar filtros (pais, precio, descuento, estado, palabra, etc.)
- Ver solo cantidad de resultados y tiempo
- Exportar Excel sin listar productos

### Requisitos adicionales

- Node.js LTS (para frontend React)
- Python 3.10+

### Levantar backend API (FastAPI)

```bash
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

### Levantar frontend React (Vite)

```bash
cd web
npm install
npm run dev
```

La UI quedara disponible en `http://127.0.0.1:5173` y usara proxy a `/api`.

Si quieres usar cookies autenticadas en local, puedes:

- escribir la ruta en el campo `Archivo cookies (opcional)`, o
- definir la variable de entorno `ML_COOKIE` con el header completo.

### Un solo comando (backend + frontend)

```bash
python3 run_dev.py
```

Este comando levanta todas las vistas disponibles:

- MercadoLibre: `http://127.0.0.1:5173`
- Facebook Marketplace: `http://127.0.0.1:5184`
- Knasta: `http://127.0.0.1:5185`
- Pulga: `http://127.0.0.1:5186`
- TuGanga: `http://127.0.0.1:5187`
- DescuentosRata: `http://127.0.0.1:8040`

Para validar arranque y apagar automáticamente:

```bash
python3 run_all.py --no-open --check
```

## Despliegue en Render

El repo ya queda preparado para Render como un solo servicio Docker:

- `Dockerfile`: compila `web/` con Vite y sirve todo desde FastAPI.
- `render.yaml`: crea un Web Service con healthcheck en `/api/health`.
- `requirements.txt`: dependencias Python del backend.

### Opcion recomendada: Blueprint

1. Sube este repo a GitHub.
2. En Render, entra a `New + > Blueprint`.
3. Selecciona el repositorio.
4. Render detectara `render.yaml` y creara el servicio.
5. En `Environment`, agrega el secret `ML_COOKIE` si necesitas sesion autenticada.

### Variables importantes

- `ML_COOKIE`: opcional. Cookie header completo de Mercado Libre. Si expira o causa
  bloqueo, la corrida diaria avisa y reintenta una vez sin cookie.
- `ML_PROXY`: opcional. Proxy HTTP/HTTPS para Mercado Libre, sin credenciales
  hardcodeadas en el repositorio.
- `ML_USER_AGENT`: opcional. User-Agent de navegador para actualizarlo sin cambiar código.
- `ML_MAX_PAGES`: máximo de páginas por búsqueda de Mercado Libre. La daily usa `20`.
- `PORT`: lo maneja Render automaticamente.

### Como funciona en produccion

- Render construye el frontend con `npm ci && npm run build`.
- FastAPI sirve la SPA compilada desde `web/dist`.
- La API queda en el mismo dominio bajo `/api/...`.

### Probar Docker localmente

```bash
docker build -t prodescuento-ml .
docker run --rm -p 10000:10000 -e ML_COOKIE="a=1; b=2" prodescuento-ml
```

Luego abre `http://127.0.0.1:10000`.

## Requisitos

- Python 3.10+
- Conexión a internet

## Uso básico

```bash
python mercadolibre.py notebook rtx --country cl --limit 20
```

## Salida JSON

```bash
python mercadolibre.py notebook rtx --country cl --limit 20 --json
```

## Traer más resultados (paginación)

```bash
python mercadolibre.py notebook rtx --country cl --all-results --max-pages 20 --json
```

Sin límite de páginas (hasta que no haya más resultados):

```bash
python mercadolibre.py notebook rtx --country cl --all-results --max-pages 0 --json
```

## Exportar a Excel (ruta automática)

```bash
python mercadolibre.py notebook rtx --country cl --all-results --max-pages 20 --sort-price --export-xlsx
```

## Exportar a Excel (ruta específica)

```bash
python mercadolibre.py notebook rtx --country cl --all-results --max-pages 20 --sort-price --export-xlsx exports\\notebook_rtx.xlsx
```

## Filtros útiles

### Precio mínimo y máximo

```bash
python mercadolibre.py notebook rtx --country cl --all-results --max-pages 20 --min-price 700000 --max-price 1800000 --export-xlsx
```

### Filtrar por palabra en el título

```bash
python mercadolibre.py notebook rtx --country cl --all-results --max-pages 20 --word victus --export-xlsx
```

### Descartar palabras en el título (múltiples)

```bash
python mercadolibre.py notebook rtx --country cl --all-results --max-pages 20 --exclude-word funda --exclude-word carcasa --export-xlsx
```

### Filtrar por descuento mínimo

```bash
python mercadolibre.py notebook rtx --country cl --all-results --max-pages 20 --min-discount 10 --export-xlsx
```

### Filtrar por condición

```bash
python mercadolibre.py notebook rtx --country cl --all-results --max-pages 20 --condition used --export-xlsx
```

Valores de `--condition`:

- `any`
- `new`
- `used`
- `reconditioned`

También puedes usar alias en español con `--estado`:

```bash
python mercadolibre.py notebook rtx --country cl --all-results --max-pages 20 --estado usado --export-xlsx
python mercadolibre.py notebook rtx --country cl --all-results --max-pages 20 --estado nuevo --export-xlsx
python mercadolibre.py notebook rtx --country cl --all-results --max-pages 20 --estado reacondicionado --export-xlsx
```

## Rendimiento

- El script imprime al final: `Tiempo total: X.XXs`.
- Ajusta `--max-pages` para equilibrar cobertura vs tiempo.
- Ajusta `--condition-workers` (default: 16) para acelerar lectura de estado.

## Notas

- Por defecto se excluyen publicaciones internacionales.
- Para incluir internacionales usa `--include-international`.
- Los excels se guardan por defecto en `exports/`.
## Sesion autenticada (cookies)

Si Mercado Libre bloquea resultados (pagina shell), puedes pasar cookies de sesion:

```bash
python mercadolibre.py celular --country cl --all-results --max-pages 0 --sort-price --export-xlsx --cookie "_d2id=...; _mldataSessionId=...; _csrf=..."
```

O desde archivo de texto:

```bash
python mercadolibre.py celular --country cl --all-results --max-pages 0 --sort-price --export-xlsx --cookie-file cookies.txt
```

`cookies.txt` debe contener una sola linea con formato `name=value; name2=value2`.

## Replicar exactamente la URL del navegador

Si quieres que el scraper use los mismos filtros/categorias de la URL del navegador:

```bash
python mercadolibre.py --search-url "https://listado.mercadolibre.cl/..." --all-results --max-pages 0 --export-xlsx --cookie-file cookies.txt
```

## Automatizacion 100% gratuita (GitHub Actions)

Puedes ejecutar busquedas diarias sin prender tu PC usando GitHub Actions.

### Archivos incluidos

- `automation/searches.json`: configuracion de busquedas.
- `automation/daily_job.py`: ejecuta scraping, genera JSON/XLSX y resumen.
- `.github/workflows/daily_scan.yml`: corrida diaria automatica.

### Como activarlo

1. Sube este repo a GitHub.
2. Ve a `Settings > Secrets and variables > Actions`.
3. (Opcional) Crea el secret `ML_COOKIE` con cookie header completo:
   - ejemplo: `_d2id=...; _csrf=...; ssid=...`
   - no agregues `Cookie:` al inicio ni comillas alrededor del valor
   - rota el secret cuando el log muestre `cookie fallback`, `anti_bot`, 403 o challenge
4. Ve a `Actions` y ejecuta manualmente `Daily MercadoLibre Scan` una vez.
5. Revisa `Artifacts` del run:
   - `automation/results/summary.md`
   - `automation/results/<grupo>/*.json`
   - `automation/results/diagnostics/mercadolibre_*.html` cuando MercadoLibre falle

La daily continúa con las demás tiendas si una fuente falla. La falla queda como
warning de Actions y se detalla en `summary.md`.

### Programacion diaria

El workflow corre diariamente a las `12:15 UTC` (cron en `.github/workflows/daily_scan.yml`).
Puedes ajustar esa hora editando:

```yaml
schedule:
  - cron: '15 12 * * *'
```

### Personalizar busquedas

Edita `automation/searches.json`. Cada entrada en `queries` permite:

- `terms`, `country`
- `min_price`, `max_price`, `min_discount`
- `condition` (`any/new/used/reconditioned`)
- `include_words`, `exclude_words`
- `all_results`, `max_pages`
- `export_xlsx`

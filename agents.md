# Guia de Contexto para Agentes de IA - Proyecto Pro Descuento

Este documento es la guia operacional del proyecto **Pro Descuento**. Su objetivo es que una IA pueda entender rapidamente la arquitectura, responsabilidades de archivos, flujos de datos, comandos y convenciones sin tener que abrir cada archivo desde cero.

Mantener este archivo actualizado es importante: cuando se agregue un scraper, endpoint, frontend, job o convencion transversal, actualizar primero esta guia o en el mismo cambio.

---

## 1. Resumen del Producto

**Pro Descuento** es una plataforma multiscraper para buscar, filtrar, comparar y exportar ofertas/descuentos desde varios comercios y agregadores, principalmente de Chile.

El sistema combina:

- Scrapers CLI en Python.
- APIs FastAPI/Uvicorn por fuente.
- Frontends React + Vite por fuente.
- Una busqueda global que consulta varias fuentes en paralelo.
- Exportacion a JSON/XLSX.
- Automatizacion diaria con GitHub Actions.
- Despliegue principal preparado para Render con Docker.

El foco del proyecto es encontrar ofertas utiles con filtros practicos: precio minimo/maximo, descuento minimo, condicion del producto, palabras incluidas/excluidas, categoria, tienda, ubicacion, disponibilidad y alcance de busqueda rapida/completa.

---

## 2. Arquitectura General

El repositorio funciona como un monorepo liviano. Cada scraper conserva su propia carpeta, backend y web, pero el backend principal tambien coordina funcionalidades globales.

Capas principales:

- **Scrapers Python**: extraen datos y normalizan resultados en listas de diccionarios.
- **Backends FastAPI**: exponen endpoints `/api/...` para count, preview, export, categorias y health.
- **Frontends Vite**: consumen `/api` mediante proxy local hacia su backend correspondiente.
- **Orquestador local**: `run_all.py` levanta todos los servicios, valida dependencias y puertos.
- **Busqueda global**: `global_search.py` importa los scrapers, corre fuentes en paralelo y fusiona resultados.
- **Automatizacion**: `automation/daily_job.py` ejecuta busquedas MercadoLibre configuradas en JSON.
- **Produccion**: `Dockerfile` compila `web/` y `server.py` sirve API + SPA compilada.

Regla mental: cada fuente debe ser independiente, pero puede participar en la busqueda global mediante un runner en `global_search.py`.

---

## 3. Stack Tecnico

- **Python**: 3.10+.
- **API**: FastAPI, Uvicorn, Pydantic.
- **Excel**: openpyxl.
- **Frontend principal**: React 19, Vite 7, Tailwind CSS 4, lucide-react, motion.
- **Frontends secundarios**: React + Vite, CSS local por servicio.
- **Despliegue**: Docker + Render Blueprint.
- **Automatizacion remota**: GitHub Actions.

Dependencias Python raiz:

- `fastapi`
- `pydantic`
- `uvicorn[standard]`
- `openpyxl`

Si un scraper necesita dependencias propias, revisar primero el `requirements.txt` de su carpeta y evitar acoplar dependencias entre scrapers.

---

## 4. Mapa de Servicios, Puertos y Entry Points

| Servicio | Carpeta | API app | API port | Web | Web port | Tipo |
| :--- | :--- | :--- | :---: | :--- | :---: | :--- |
| MercadoLibre / Core | raiz + `web/` | `server:app` | `8000` | `web/` | `5173` | Vite |
| Facebook Marketplace | `facebook_marketplace/` | `server_http:app` | `8010` | `facebook_marketplace/web/` | `5184` | Vite |
| Pulga | `pulga/` | `server:app` | `8015` | `pulga/web/` | `5186` | Vite |
| Knasta | `knasta_scraper/` | `server:app` | `8020` | `knasta_scraper/web/` | `5185` | Vite |
| SoloTodo | `solotodo_scraper/` | `solotodo_server:app` | `8001` | `solotodo_scraper/web/` | `5188` | Vite |
| Travel Tienda | `travel_scraper/` | `server:app` | `8050` | `travel_scraper/web/` | `5189` | Vite |
| TuGanga | `tuganga_scraper/` | `server:app` | `8030` | `tuganga_scraper/web/` | `5187` | Vite |
| DescuentosRata | `descuentosrata_scraper/` | `server:app` | `8040` | `descuentosrata_scraper/web/` | `8040` | HTML estatico servido por API |

La fuente de verdad de este mapa es `run_all.py`, lista `SERVICES`.

---

## 5. Comandos Esenciales

Desde la raiz del repo:

```bash
python run_dev.py
```

Levanta todos los backends y frontends, instala dependencias si faltan y abre las URLs.

```bash
python run_all.py --no-open --check
```

Valida dependencias y arranque de servicios sin dejarlos corriendo. Es el smoke test recomendado despues de cambios de infraestructura.

```bash
python run_all.py --services mercadolibre pulga --no-open
```

Levanta solo servicios seleccionados. Los nombres validos son los `key` de `run_all.py`: `mercadolibre`, `facebook`, `pulga`, `knasta`, `solotodo`, `travel`, `tuganga`, `descuentosrata`.

```bash
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

Levanta solo el backend principal.

```bash
cd web
npm ci
npm run dev
```

Levanta solo el frontend principal. El proxy `/api` apunta a `http://127.0.0.1:8000`.

---

## 6. Directorio Raiz: MercadoLibre y Core

Archivos principales:

- `mercadolibre.py`: scraper CLI principal. Busca en MercadoLibre, pagina resultados, aplica filtros, detecta condicion, excluye internacionales por defecto y exporta JSON/XLSX.
- `server.py`: backend FastAPI principal. Expone API para MercadoLibre, cookies, busqueda global y sirve `web/dist` en produccion.
- `global_search.py`: coordinador multiscraper. Importa runners de todas las fuentes, ejecuta en paralelo, filtra, deduplica por fuente y escribe resultados en `exports/global_<query>_<timestamp>/`.
- `category_suggest.py`: apoyo para sugerencias/categorias de MercadoLibre.
- `run_all.py`: orquestador de desarrollo multiservicio.
- `run_dev.py`: wrapper directo a `run_all.main`.
- `Dockerfile`: build multi-etapa para frontend principal + backend FastAPI.
- `render.yaml`: definicion Render Blueprint.
- `requirements.txt`: dependencias Python del backend principal.
- `cookies.txt`: cookie local opcional para MercadoLibre. Tratar como dato sensible.
- `exports/`: salidas locales generadas por scrapers y busqueda global.
- `automation/`: job diario MercadoLibre.
- `web/`: frontend principal React/Vite.

Endpoints principales en `server.py`:

- `POST /api/count`: conteo aproximado MercadoLibre.
- `POST /api/count-exact`: conteo exacto/captura mas completa MercadoLibre.
- `POST /api/export`: genera XLSX MercadoLibre.
- `POST /api/preview`: obtiene vista previa MercadoLibre.
- `POST /api/categories`: categorias MercadoLibre.
- `POST /api/global-search`: inicia busqueda global asincrona.
- `GET /api/global-search/{job_id}`: consulta estado/resultado de busqueda global.
- `GET /api/global-categories`: categorias/opciones para busqueda global.
- `POST /api/cookies`: guarda/configura cookies de MercadoLibre.
- `GET /api/cookies/status`: estado de cookies MercadoLibre.
- `POST /api/facebook-cookies`: guarda/configura cookies Facebook desde el backend principal.
- `GET /api/facebook-cookies/status`: estado de cookies Facebook.
- `GET /api/health`: healthcheck.

---

## 7. MercadoLibre CLI

Uso basico:

```bash
python mercadolibre.py notebook rtx --country cl --limit 20
```

Exportar Excel:

```bash
python mercadolibre.py notebook rtx --country cl --all-results --max-pages 20 --sort-price --export-xlsx
```

Filtros comunes:

```bash
python mercadolibre.py celular --country cl --min-price 100000 --max-price 500000 --min-discount 15 --condition used --export-xlsx
```

Replicar una URL del navegador:

```bash
python mercadolibre.py --search-url "https://listado.mercadolibre.cl/..." --cookie-file cookies.txt --export-xlsx
```

Notas de comportamiento:

- Por defecto excluye publicaciones internacionales.
- `--include-international` las vuelve a incluir.
- `--all-results --max-pages 0` intenta recorrer hasta que no haya mas paginas.
- `--condition` acepta `any`, `new`, `used`, `reconditioned`.
- Las cookies pueden venir por `--cookie`, `--cookie-file` o variable `ML_COOKIE`.

---

## 8. Busqueda Global

La busqueda global vive en `global_search.py` y se usa desde `server.py` con los endpoints `/api/global-search`.

Fuentes soportadas:

- `mercadolibre`
- `facebook_marketplace`
- `pulga`
- `knasta`
- `solotodo`
- `travel`
- `tuganga`
- `descuentosrata`

Flujo:

1. `build_config(raw)` normaliza input de la UI/API.
2. Cada fuente se ejecuta con su runner `_run_<fuente>`.
3. Los runners llaman a funciones publicas del scraper correspondiente.
4. `_filter_words` aplica filtros transversales de include/exclude, modo estricto y filtro inteligente.
5. Cada resultado por fuente se escribe como JSON.
6. Se fusiona todo en `all_results.json`.
7. Se escribe `_summary.json`.

Campos de configuracion global relevantes:

- `query`
- `sources`
- `scan_scope`: `fast` o `complete`
- `max_items_per_source`
- `min_price`, `max_price`, `min_discount`
- `include_words`, `exclude_words`
- `strict_mode`
- `smart_filter`
- `sort_price`
- `include_international`
- Campos especificos por fuente: `facebook_radius_km`, `pulga_category`, `knasta_retails`, `solotodo_category_id`, `travel_category_id`, `tuganga_stores`, `descuentosrata_all`, etc.

Importante:

- Si se agrega una nueva fuente al proyecto, no basta con crear su carpeta. Tambien hay que agregar runner en `global_search.py`, endpoint/categorias si aplica, UI en `web/src/global-search`, y servicio en `run_all.py` si tiene API/web propia.
- La deduplicacion global actual conserva duplicados entre fuentes distintas; deduplica usando `source:key`.
- El filtro inteligente descarta accesorios fuertes si parecen irrelevantes para la consulta. Revisar `_filter_words` antes de cambiar comportamiento de relevancia.

---

## 9. Frontend Principal (`web/`)

La SPA principal usa React + Vite + Tailwind. Es la UI mas importante del proyecto.

Archivos clave:

- `web/src/App.jsx`: aplicacion principal MercadoLibre y/o integracion de vistas principales.
- `web/src/App.css` y `web/src/index.css`: estilos base.
- `web/src/main.jsx`: entrypoint React.
- `web/vite.config.js`: plugin React, Tailwind y proxy `/api` a `127.0.0.1:8000`.
- `web/package.json`: scripts `dev`, `build`, `lint`, `preview`.

Modulo de busqueda global:

- `web/src/global-search/GlobalSearchView.jsx`: vista/contenedor principal de busqueda global.
- `web/src/global-search/GlobalSearchTerminal.jsx`: terminal/formulario de parametros.
- `web/src/global-search/GlobalSearchResultsModal.jsx`: modal de resultados.
- `web/src/global-search/GlobalSearchRadar.jsx`: visualizacion radar/estado de fuentes.
- `web/src/global-search/GlobalSearchFilterModal.jsx`: filtros avanzados.
- `web/src/global-search/GlobalSearchCategoryControls.jsx`: controles por categoria/fuente.
- `web/src/global-search/GlobalSearchHUD.jsx`: indicadores/resumen.
- `web/src/global-search/GlobalSearchNavbar.jsx`: navegacion interna.
- `web/src/global-search/globalSearchNodes.js`: definicion de nodos/fuentes visuales.
- `web/src/global-search/soundService.js`: sonidos/feedback.
- `web/src/global-search/matrix-theme.css`: tema visual de esta experiencia.

Reglas para cambios UI:

- Mantener los contratos con `/api` y el proxy.
- Evitar introducir librerias pesadas si CSS/React local basta.
- Si se agrega un filtro nuevo, actualizar estado UI, payload hacia backend, defaults en `global_search.py` y documentacion.
- Validar responsive: modales, tablas y controles no deben desbordar en mobile.
- Los iconos deben preferir `lucide-react` si ya esta disponible.

---

## 10. Frontends Secundarios

Cada scraper con web Vite tiene estructura similar:

- `web/src/App.jsx`
- `web/src/App.css`
- `web/src/index.css`
- `web/src/main.jsx`
- `web/vite.config.js`
- `web/package.json`

Proxy por servicio:

- `web/`: `/api` -> `127.0.0.1:8000`
- `facebook_marketplace/web/`: `/api` -> `127.0.0.1:8010`
- `pulga/web/`: `/api` -> `127.0.0.1:8015`
- `tuganga_scraper/web/`: `/api` -> `127.0.0.1:8030`

Algunos `vite.config.js` no declaran puerto/proxy explicitamente porque el puerto lo fuerza `run_all.py` al invocar Vite con `--port`.

---

## 11. Facebook Marketplace

Carpeta: `facebook_marketplace/`

Responsabilidad: scraping de Facebook Marketplace con soporte de cookies/perfiles, ubicacion, radio y filtros de precio/palabras.

Archivos clave:

- `facebook_api.py`: logica principal reutilizable desde API y busqueda global. Contiene opciones de busqueda, carga de perfiles/cookies y ejecucion.
- `facebook_marketplace.py`: CLI/scraper orientado a Marketplace.
- `server_http.py`: API usada por `run_all.py` en el puerto `8010`.
- `server.py`: API alternativa/historica con endpoints similares.
- `login_facebook.py`, `import_browser_cookies.py`, `import_cookie_text.py`: utilidades para cookies/sesion.
- `fb_cookie_profiles.json`, `fb_cookies.json`, `fb_cookies_talca.json`, `facebook_cookies.txt`, `storage_state.json`: datos de sesion/cookies. Tratar como sensibles.
- `automation/`: automatizacion especifica de Facebook si se usa.
- `web/`: UI Vite de Facebook Marketplace.

Endpoints `server_http.py`:

- `GET /api/cookies/status`
- `POST /api/cookies`
- `DELETE /api/cookies`
- `POST /api/count-exact`
- `POST /api/preview`
- `POST /api/export`
- `GET /api/health`

Notas:

- No mezclar cookies reales en commits.
- Facebook cambia markup/endpoints con frecuencia; aislar hacks en `facebook_api.py` o utilidades de Facebook.
- La busqueda global usa `facebook_api.execute_search`.

---

## 12. Pulga

Carpeta: `pulga/`

Responsabilidad: busqueda y exportacion desde Pulga.cl.

Archivos:

- `pulga.py`: scraper y filtros.
- `server.py`: API FastAPI puerto `8015`.
- `run_dev.py`: levantamiento puntual del servicio.
- `requirements.txt`: dependencias propias si aplica.
- `web/`: UI Vite.

Endpoints:

- `POST /api/count`
- `POST /api/preview`
- `POST /api/export`
- `GET /api/categories`
- `GET /api/health`

Busqueda global:

- Importa `pulga`.
- Usa `collect_results(...)` y `apply_filters(...)`.
- Campo relevante: `pulga_category`, `pulga_condition`, `pulga_city`, `pulga_word`.

---

## 13. Knasta

Carpeta: `knasta_scraper/`

Responsabilidad: consulta de ofertas, categorias, retails e historial/ofertas desde Knasta.

Archivos:

- `knasta_api.py`: API interna del scraper y `SearchOptions`.
- `server.py`: API FastAPI puerto `8020`.
- `analyze*.py`, `find_*.py`, `check_limit.py`: scripts de investigacion/debug. No son parte critica del runtime normal.
- `README.md`, `requirements.txt`, `run_dev.py`.
- `web/`: UI Vite.

Endpoints:

- `POST /api/search`
- `GET /api/categories`
- `GET /api/retails`
- `GET /api/health`

Busqueda global:

- Usa `knasta_api.SearchOptions` y `knasta_api.execute_search`.
- Campos relevantes: `knasta_retails`, `knasta_knastaday`, `knasta_category`.
- En modo `complete` puede usar muchas paginas; cuidar limites y tiempos.

---

## 14. SoloTodo

Carpeta: `solotodo_scraper/`

Responsabilidad: busqueda/comparacion de productos tecnologicos usando datos/API de SoloTodo.

Archivos:

- `solotodo.py`: scraper, categorias, productos, precios y filtros.
- `solotodo_server.py`: API FastAPI puerto `8001`.
- `README.md`, `requirements.txt`, `run_dev.py`.
- `web/`: UI Vite.

Endpoints:

- `GET /api/categories`
- `POST /api/categories`
- `POST /api/count`
- `POST /api/preview`
- `POST /api/export`
- `GET /api/health`

Busqueda global:

- Usa `collect_browse_results(...)` y `apply_filters(...)`.
- Campos relevantes: `solotodo_category_id`, `solotodo_country_id`, `solotodo_ordering`.
- `solotodo_category_id = 0` significa todas las categorias; no convertirlo accidentalmente a default.

---

## 15. Travel Tienda

Carpeta: `travel_scraper/`

Responsabilidad: busqueda de productos/ofertas en Travel Tienda.

Archivos:

- `travel.py`: scraper y filtros.
- `server.py`: API FastAPI puerto `8050`.
- `README.md`, `requirements.txt`, `run_dev.py`.
- `web/`: UI Vite.

Endpoints:

- `GET /api/categories`
- `POST /api/categories`
- `POST /api/count`
- `POST /api/preview`
- `POST /api/export`
- `GET /api/health`

Busqueda global:

- Usa `collect_results(...)` y `apply_filters(...)`.
- Campos relevantes: `travel_category_id`, `travel_ordering`.

---

## 16. TuGanga

Carpeta: `tuganga_scraper/`

Responsabilidad: busqueda de ofertas agrupadas desde TuGanga.

Archivos:

- `tuganga_api.py`: scraper, `SearchOptions`, ejecucion.
- `server.py`: API FastAPI puerto `8030`.
- `web/`: UI Vite.

Endpoints:

- `POST /api/search`
- `GET /api/categories`
- `GET /api/health`

Busqueda global:

- Usa `tuganga_api.SearchOptions` y `tuganga_api.execute_search`.
- Campos relevantes: `tuganga_mode`, `tuganga_stores`, `tuganga_categories`, `tuganga_only_available`, `tuganga_sort`.
- Si hay `query`, `global_search.py` fuerza `tuganga_mode = "search"`.

---

## 17. DescuentosRata

Carpeta: `descuentosrata_scraper/`

Responsabilidad: extraccion de publicaciones/ofertas desde DescuentosRata.

Archivos:

- `descuentosrata_api.py`: scraper, `SearchOptions`, ejecucion.
- `server.py`: API FastAPI puerto `8040`.
- `web/index.html`: UI estatica HTML/JS servida por el mismo backend.
- `requirements.txt`.

Endpoints:

- `POST /api/preview`
- `POST /api/export`
- `GET /api/health`
- `GET /`

Busqueda global:

- Usa `descuentosrata_api.execute_search`.
- Campos relevantes: `descuentosrata_all`, `descuentosrata_limit`.
- Puede buscar todo (`descuentosrata_all = true`) aunque la consulta principal este vacia.

---

## 18. Automatizacion

Carpeta: `automation/`

Archivos:

- `automation/searches.json`: configuracion de consultas diarias.
- `automation/daily_job.py`: ejecuta `mercadolibre.py`, genera JSON/XLSX y `summary.md`.
- `automation/runs/`: historial local de ejecuciones.

Flujo de `daily_job.py`:

1. Lee `searches.json`.
2. Construye comandos CLI para `mercadolibre.py`.
3. Ejecuta cada busqueda con `subprocess.run`.
4. Extrae JSON desde stdout.
5. Guarda JSON por consulta.
6. Guarda XLSX si corresponde.
7. Crea `all_results.json`.
8. Crea `summary.md` con top 20 por descuento alto + precio bajo.

Campos esperados en cada query:

- `name`
- `terms`
- `country`
- `min_price`, `max_price`, `min_discount`
- `condition`
- `include_words`, `exclude_words`
- `all_results`, `max_pages`
- `sort_price`
- `include_international`
- `export_xlsx`

Antes de modificar automatizacion, revisar `.github/workflows/daily_scan.yml` si existe en la rama. Cualquier cambio de outputs debe mantener artifacts esperados: `summary.md`, `all_results.json`, JSON/XLSX por busqueda.

---

## 19. Despliegue y Produccion

El despliegue principal empaqueta solo la aplicacion core MercadoLibre/global:

- Construye `web/` con Vite.
- Sirve `web/dist` desde `server.py`.
- Expone API bajo `/api/...`.
- Usa `PORT` definido por Render.
- Healthcheck: `/api/health`.

Archivos:

- `Dockerfile`
- `render.yaml`

Probar local:

```bash
docker build -t prodescuento .
docker run --rm -p 10000:10000 -e ML_COOKIE="a=1; b=2" prodescuento
```

Abrir:

```text
http://127.0.0.1:10000
```

Nota: los servicios secundarios no necesariamente quedan desplegados como procesos separados en este Dockerfile. No asumir que una web secundaria esta disponible en produccion salvo que se haya agregado explicitamente al despliegue.

---

## 20. Datos, Salidas y Archivos Sensibles

Salidas generadas:

- `exports/`
- `exports/global_<query>_<timestamp>/`
- `automation/runs/`
- `global_search_*.json`
- capturas o archivos temporales en carpetas de mockup/debug.

Datos sensibles o personales:

- `cookies.txt`
- `facebook_marketplace/facebook_cookies.txt`
- `facebook_marketplace/fb_cookies*.json`
- `facebook_marketplace/storage_state.json`
- perfiles Chrome dentro de `facebook_marketplace/chrome_profile/`, `facebook_marketplace/williams/`, `facebook_marketplace/menos20k@gmail.com/`

Reglas:

- No imprimir cookies completas en logs, docs o respuestas.
- No mover ni borrar perfiles/cookies sin pedir confirmacion.
- No depender de rutas absolutas de usuario si se puede usar `Path(__file__)`.

---

## 21. Carpetas Auxiliares o de Referencia

Estas carpetas pueden servir como referencia, pero no son runtime principal:

- `_ref_mercadolibre_ui/`: referencia UI TypeScript/React.
- `_design_import/`: importacion/diseño experimental.
- `pro_descuento_mockup_figma/`: mockups/capturas.
- `presentacion_soluciones/`: material de presentacion.
- `scratch/`: scripts temporales de inspeccion.

No refactorizar ni borrar estas carpetas como parte de cambios funcionales salvo que la tarea lo pida.

---

## 22. Convenciones de Desarrollo para IA

Antes de cambiar codigo:

- Leer el archivo objetivo y los contratos cercanos.
- Buscar endpoints/funciones existentes con `rg`.
- Identificar si el cambio afecta solo una fuente o tambien busqueda global/UI/automatizacion.

Python:

- Usar `.venv/` cuando exista.
- Agregar dependencias a `requirements.txt` correspondiente.
- Mantener scrapers desacoplados.
- Usar timeouts y headers realistas en scraping.
- No romper firmas usadas por APIs o `global_search.py`.
- Si una funcion devuelve items, preservar nombres de campos que la UI ya usa: `title`, `name`, `price`, `link`, `url`, `image`, `discount_percent`, `condition`, `store`, `category`, etc.

FastAPI:

- Mantener endpoints bajo `/api`.
- Mantener `GET /api/health` por servicio.
- Preservar CORS permisivo para desarrollo local salvo requerimiento explicito.
- Si se sirve SPA, montar assets y fallback a `index.html` solo cuando exista `dist`.

Frontend:

- Respetar proxies Vite.
- Mantener UI responsiva.
- No hardcodear puertos en componentes si ya se usa `/api`.
- Mantener estados de carga, error y vacio.
- Si se agrega un nuevo campo de filtro, documentar y conectar backend + UI.

Scraping:

- Los sitios externos cambian. Aislar parsing fragil en el scraper de esa fuente.
- Preferir normalizacion defensiva sobre asumir campos siempre presentes.
- No hacer loops ilimitados sin limite, timeout o corte por paginas.
- En modo `complete`, cuidar tiempo y volumen.

Git:

- El repo puede estar sucio. No revertir cambios ajenos.
- No borrar outputs/cookies/perfiles sin indicacion explicita.

---

## 23. Checklist para Agregar una Nueva Fuente

1. Crear carpeta del scraper con modulo Python principal.
2. Definir una funcion reusable tipo `execute_search` o `collect_results`.
3. Normalizar resultados a diccionarios con campos comunes.
4. Crear `server.py` FastAPI con `/api/health` y endpoints necesarios.
5. Crear `web/` si necesita UI propia.
6. Agregar servicio en `run_all.py` con puertos no ocupados.
7. Agregar runner en `global_search.py`.
8. Agregar source a `DEFAULT_SOURCES` si debe participar por defecto.
9. Agregar controles/opciones en `web/src/global-search`.
10. Actualizar este `agents.md`.
11. Probar con `python run_all.py --services <nuevo> --no-open --check`.

---

## 24. Checklist para Agregar un Filtro Global

1. Agregar default y normalizacion en `global_search.build_config`.
2. Pasar el campo al runner de cada fuente que lo soporte.
3. Ajustar filtros transversales si aplica.
4. Agregar control en `GlobalSearchTerminal.jsx` o `GlobalSearchFilterModal.jsx`.
5. Mostrar resumen/estado si corresponde en HUD o resultados.
6. Mantener compatibilidad cuando el campo no venga desde clientes antiguos.
7. Probar busqueda rapida con 2 o 3 fuentes.

---

## 25. Pruebas y Verificacion Recomendada

No hay una suite unica consolidada. Usar verificaciones segun el cambio:

Backend principal:

```bash
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

Frontend principal:

```bash
cd web
npm run build
```

Todos los servicios:

```bash
python run_all.py --no-open --check
```

MercadoLibre CLI:

```bash
python mercadolibre.py notebook --country cl --limit 5 --json
```

Automatizacion:

```bash
python automation/daily_job.py --config automation/searches.json --output-dir automation/runs
```

Si el cambio toca UI, validar tambien en navegador local. Si toca scraping real, considerar que fallas pueden deberse a bloqueo/red/sitio externo; reportar claramente esa posibilidad.

---

## 26. Problemas Frecuentes

- **Puerto ocupado**: `run_all.py` detecta puertos abiertos y puede reutilizarlos. Revisar puertos 8000, 8001, 8010, 8015, 8020, 8030, 8040, 8050 y webs 5173/5184/5185/5186/5187/5188/5189.
- **Vite sin dependencias**: ejecutar `npm ci` dentro del `web/` correspondiente o dejar que `run_all.py` lo haga.
- **MercadoLibre devuelve shell/bloqueo**: usar `ML_COOKIE`, `cookies.txt` o `--cookie-file`.
- **Facebook no devuelve datos**: revisar cookies/perfil, ubicacion, radio y cambios del sitio.
- **Resultados irrelevantes**: revisar `include_words`, `exclude_words`, `strict_mode` y `smart_filter`.
- **Categoria "todas" en SoloTodo**: no reemplazar `0` por default; `global_search.py` tiene helpers para preservar ese valor.
- **Produccion no muestra UI**: verificar que `web/dist` exista y que Docker haya corrido `npm ci && npm run build`.

---

## 27. Principio de Mantenimiento

El proyecto crece por fuentes. Mantener cada scraper aislado, pero conectar solo lo necesario en estos puntos transversales:

- `run_all.py` para desarrollo local.
- `global_search.py` para busqueda multiscraper.
- `server.py` si la UI principal necesita exponerlo.
- `web/src/global-search/` si afecta la experiencia global.
- `agents.md` para que futuras IA no tengan que redescubrir la arquitectura.

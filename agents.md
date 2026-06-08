# Guia de Contexto para Agentes de IA - Proyecto Pro Descuento

Este documento es la guia operacional del proyecto **Pro Descuento**. Su objetivo es que una IA pueda entender rapidamente la arquitectura, responsabilidades de archivos, flujos de datos, comandos y convenciones sin tener que abrir cada archivo desde cero.

Mantener este archivo actualizado es importante: cuando se agregue un scraper, endpoint, frontend, job o convencion transversal, actualizar primero esta guia o en el mismo cambio.

---

## 1. Resumen del Producto

**Pro Descuento** es una plataforma multiscraper para buscar, filtrar, comparar y exportar ofertas/descuentos desde varios comercios y agregadores, principalmente de Chile.

La interfaz unica del proyecto es la **busqueda conjunta (global search)**, que consulta multiples fuentes en paralelo y presenta los resultados unificados.

El sistema combina:

- Scrapers Python por fuente (MercadoLibre, Facebook Marketplace, Pulga, Knasta, SoloTodo, Travel Tienda, TuGanga, DescuentosRata, PcFactory, AliExpress).
- Un backend FastAPI principal (`server.py`) que expone la API de busqueda global, cookies y categorias.
- Un frontend React + Vite unico (`web/`) con la experiencia de busqueda conjunta.
- Exportacion a JSON.
- Automatizacion diaria con GitHub Actions.
- Despliegue preparado para Render con Docker.

> **Nota historica**: anteriormente cada fuente tenia su propio backend HTTP y frontend Vite individual. Esos archivos pueden seguir en disco pero ya **no se levantan ni se usan**. Toda la funcionalidad pasa por la busqueda conjunta.

El foco del proyecto es encontrar ofertas utiles con filtros practicos: precio minimo/maximo, descuento minimo, condicion del producto, palabras incluidas/excluidas, categoria, tienda, ubicacion, disponibilidad y alcance de busqueda rapida/completa.

---

## 2. Arquitectura General

El repositorio funciona como un monorepo liviano. Los scrapers viven en carpetas independientes como modulos Python, pero solo se consumen a traves de la busqueda global.

Capas principales:

- **Scrapers Python**: extraen datos y normalizan resultados en listas de diccionarios. Son importados directamente por `global_search.py`.
- **Backend FastAPI unico**: `server.py` en la raiz expone endpoints `/api/...` para busqueda global, categorias, cookies y health.
- **Frontend unico**: `web/` contiene la SPA React/Vite con la experiencia de busqueda conjunta.
- **Orquestador local**: `run_all.py` levanta el backend + frontend principal.
- **Busqueda global**: `global_search.py` importa los scrapers, corre fuentes en paralelo y fusiona resultados.
- **Automatizacion**: `automation/daily_job.py` ejecuta busquedas MercadoLibre configuradas en JSON.
- **Produccion**: `Dockerfile` compila `web/` y `server.py` sirve API + SPA compilada.

Regla clave: **no hay vistas individuales por fuente**. Los scrapers solo participan como modulos Python importados por `global_search.py`.

---

## 3. Stack Tecnico

- **Python**: 3.10+.
- **API**: FastAPI, Uvicorn, Pydantic.
- **Excel**: openpyxl.
- **Frontend**: React 19, Vite 7, Tailwind CSS 4, lucide-react, motion.
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

Solo hay un servicio activo:

| Servicio | Carpeta | API app | API port | Web | Web port | Tipo |
| :--- | :--- | :--- | :---: | :--- | :---: | :--- |
| Pro Descuento (busqueda conjunta) | raiz + `web/` | `server:app` | `8000` | `web/` | `5173` | Vite |

La fuente de verdad de este mapa es `run_all.py`, lista `SERVICES`.

> Los backends y frontends individuales de cada scraper (puertos 8001, 8010, 8015, 8020, 8030, 8040, 8050 y sus webs) **ya no se levantan**. Los archivos pueden existir en disco pero no forman parte del flujo activo.

---

## 5. Comandos Esenciales

Desde la raiz del repo:

```bash
python run_dev.py
```

Levanta el backend y frontend principal, instala dependencias si faltan y abre la URL.

```bash
python run_all.py --no-open --check
```

Valida dependencias y arranque del servicio sin dejarlo corriendo. Es el smoke test recomendado despues de cambios de infraestructura.

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

## 6. Directorio Raiz y Core

Archivos principales:

- `mercadolibre.py`: scraper CLI principal. Busca en MercadoLibre, pagina resultados, aplica filtros, detecta condicion, excluye internacionales por defecto y exporta JSON/XLSX.
- `server.py`: backend FastAPI unico. Expone API de busqueda global, cookies y sirve `web/dist` en produccion.
- `global_search.py`: coordinador multiscraper. Importa runners de todas las fuentes, ejecuta en paralelo, filtra, deduplica por fuente y escribe resultados en `exports/global_<query>_<timestamp>/`.
- `category_suggest.py`: apoyo para sugerencias/categorias automaticas en la busqueda global.
- `run_all.py`: orquestador de desarrollo (un solo servicio).
- `run_dev.py`: wrapper directo a `run_all.main`.
- `Dockerfile`: build multi-etapa para frontend + backend FastAPI.
- `render.yaml`: definicion Render Blueprint.
- `requirements.txt`: dependencias Python del backend principal.
- `cookies.txt`: cookie local opcional para MercadoLibre. Tratar como dato sensible.
- `exports/`: salidas locales generadas por scrapers y busqueda global.
- `automation/`: job diario MercadoLibre.
- `web/`: frontend unico React/Vite (busqueda conjunta).

Endpoints en `server.py`:

- `POST /api/global-search`: inicia busqueda global asincrona.
- `GET /api/global-search/{job_id}`: consulta estado/resultado de busqueda global.
- `GET /api/global-categories`: categorias/opciones para busqueda global.
- `POST /api/cookies`: guarda/configura cookies de MercadoLibre.
- `GET /api/cookies/status`: estado de cookies MercadoLibre.
- `POST /api/facebook-cookies`: guarda/configura cookies Facebook.
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

## 8. Busqueda Global (Funcionalidad Central)

La busqueda global vive en `global_search.py` y se usa desde `server.py` con los endpoints `/api/global-search`. **Esta es la funcionalidad central y unica de la interfaz web.**

Fuentes soportadas:

- `mercadolibre`
- `facebook_marketplace`
- `pulga`
- `knasta`
- `solotodo`
- `travel`
- `tuganga`
- `descuentosrata`
- `pcfactory`
- `aliexpress`
- `jumbo`
- `santaisabel`
- `unimarc`
- `alvi`
- `lider`
- `acuenta`
- `tottus`

Flujo:

1. `build_config(raw)` normaliza input de la UI/API.
2. Cada fuente se ejecuta con su runner `_run_<fuente>`.
3. Los runners llaman a funciones publicas del scraper correspondiente (importado como modulo Python, sin pasar por HTTP).
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
- Campos especificos por fuente: `facebook_radius_km`, `pulga_category`, `knasta_retails`, `solotodo_category_id`, `travel_category_id`, `tuganga_stores`, `descuentosrata_all`, `pcfactory_word`, `pcfactory_category_id`, `aliexpress_word`, `aliexpress_category_id`, `jumbo_category_id`, `santaisabel_category_id`, `unimarc_category_id`, `alvi_category_id`, `lider_category_id`, `acuenta_category_id`, `tottus_category_id`, etc.

Importante:

- Si se agrega una nueva fuente al proyecto, hay que: crear el modulo scraper Python, agregar runner en `global_search.py`, agregar source a `DEFAULT_SOURCES`, agregar controles en `web/src/global-search`, y actualizar este `agents.md`.
- La deduplicacion global actual conserva duplicados entre fuentes distintas; deduplica usando `source:key`.
- El filtro inteligente descarta accesorios fuertes si parecen irrelevantes para la consulta. Revisar `_filter_words` antes de cambiar comportamiento de relevancia.

---

## 9. Frontend (`web/`)

La SPA usa React + Vite + Tailwind. Es la **unica interfaz web del proyecto** y muestra exclusivamente la busqueda conjunta.

Archivos clave:

- `web/src/App.jsx`: aplicacion principal. Gestiona estado global, cookies, busqueda global y renderiza `<GlobalSearchView />`.
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
- `web/src/components/SupermercadosPanel.jsx`: pestaña separada de supermercados. Usa los mismos endpoints `/api/global-search` y `/api/global-categories`, pero limita `sources` a Jumbo, Santa Isabel, Unimarc, Alvi, Lider, acuenta y Tottus.

Reglas para cambios UI:

- Mantener los contratos con `/api` y el proxy.
- Evitar introducir librerias pesadas si CSS/React local basta.
- Si se agrega un filtro nuevo, actualizar estado UI, payload hacia backend, defaults en `global_search.py` y documentacion.
- Validar responsive: modales, tablas y controles no deben desbordar en mobile.
- Los iconos deben preferir `lucide-react` si ya esta disponible.

---

## 10. Scrapers por Fuente (Modulos Python)

Los scrapers viven en carpetas independientes. Ya **no tienen backends HTTP ni frontends activos**. Se importan directamente como modulos Python por `global_search.py`.

### Facebook Marketplace (`facebook_marketplace/`)

- `facebook_api.py`: logica principal. Contiene `SearchOptions`, `execute_search`, carga de perfiles/cookies.
- `facebook_marketplace.py`: CLI/scraper.
- Archivos de cookies/sesion: tratar como sensibles.
- La busqueda global usa `facebook_api.execute_search`.

### Pulga (`pulga/`)

- `pulga.py`: scraper y filtros.
- La busqueda global usa `collect_results(...)` y `apply_filters(...)`.
- Campos: `pulga_category`, `pulga_condition`, `pulga_city`, `pulga_word`.

### Knasta (`knasta_scraper/`)

- `knasta_api.py`: scraper, `SearchOptions`, `execute_search`.
- La busqueda global usa `knasta_api.SearchOptions` y `knasta_api.execute_search`.
- Campos: `knasta_retails`, `knasta_knastaday`, `knasta_category`.

### SoloTodo (`solotodo_scraper/`)

- `solotodo.py`: scraper, categorias, productos, precios y filtros.
- La busqueda global usa `collect_browse_results(...)` y `apply_filters(...)`.
- Campos: `solotodo_category_id`, `solotodo_country_id`, `solotodo_ordering`.
- `solotodo_category_id = 0` significa todas las categorias.

### Travel Tienda (`travel_scraper/`)

- `travel.py`: scraper y filtros.
- La busqueda global usa `collect_results(...)` y `apply_filters(...)`.
- Campos: `travel_category_id`, `travel_ordering`.

### TuGanga (`tuganga_scraper/`)

- `tuganga_api.py`: scraper, `SearchOptions`, `execute_search`.
- La busqueda global usa `tuganga_api.SearchOptions` y `tuganga_api.execute_search`.
- Campos: `tuganga_mode`, `tuganga_stores`, `tuganga_categories`, `tuganga_only_available`, `tuganga_sort`.

### DescuentosRata (`descuentosrata_scraper/`)

- `descuentosrata_api.py`: scraper, `SearchOptions`, `execute_search`.
- La busqueda global usa `descuentosrata_api.execute_search`.
- Campos: `descuentosrata_all`, `descuentosrata_limit`.

### PcFactory (`pcfactory_scraper/`)

- `pcfactory.py`: scraper que consulta productos de PcFactory Chile.
- La busqueda global usa `pcfactory.collect_results(...)` y `pcfactory.apply_filters(...)`.
- Campos: `pcfactory_word`, `pcfactory_category_id`.
- Implementacion actual: consulta directamente la API interna real de pcFactory (`/pcfactory-services-catalogo/v1/catalogo/productos?search=...&size=48`), sin depender de TuGanga.
- Las categorias se obtienen desde el menu oficial de pcFactory (`/api-dex-catalog/v1/catalog/category/PCF/menu`) y se filtran localmente por `categoria.id`, ya que el endpoint de busqueda no respeta filtros de categoria de forma confiable.
- Este scraper siempre debe ejecutar busqueda completa (todas las paginas disponibles), descargando paginas en paralelo con `ThreadPoolExecutor` para mantener velocidad.

### AliExpress (`aliexpress_scraper/`)

- `aliexpress.py`: scraper Playwright para resultados internacionales de AliExpress normalizados a costo final estimado para Chile.
- La busqueda global usa `aliexpress.collect_results(...)` y `aliexpress.apply_filters(...)`.
- Campos: `aliexpress_word`, `aliexpress_category_id`, `aliexpress_price_includes_chile_vat`.
- Requiere `Playwright` + `playwright-stealth`; despues de instalar dependencias ejecutar `playwright install chromium`.
- Para obtener precios y envios orientados a Chile, inyecta la cookie regional `aep_usuc_f` con valor `site=glo&c_tp=CLP&region=CL&b_locale=es_CL`.
- Extrae datos del JSON incrustado en scripts de inicializacion como `window.runParams` o equivalentes.
- Las categorias de AliExpress se exponen como arbol local de navegacion principal/subcategoria. Se usan como terminos guia de busqueda porque AliExpress no expone un filtro de categoria estable como pcFactory.
- Impuestos de internacion a Chile:
  - Compras hasta US$ 500: IVA 19%; arancel aduanero 0%.
  - Compras sobre US$ 500: arancel 6% sobre CIF, IVA 19% sobre CIF + arancel, y costo estimado de internacion courier de $15.000 CLP.

### Supermercados (`vtex_scraper/`, `lider_scraper/`, `tottus_scraper/`)

- Fuentes: `jumbo`, `santaisabel`, `unimarc`, `alvi`, `lider`, `acuenta`, `tottus`.
- La busqueda global usa runners en `global_search.py` con el mismo contrato `fetch_categories()`, `collect_results(...) -> (items, meta)` y `apply_filters(...)`.
- La UI no mezcla estas fuentes en los checkboxes del radar global; viven en la pestaña separada "Supermercados" y llaman al mismo endpoint `/api/global-search`.
- VTEX/SMU: `jumbo`, `santaisabel`, `unimarc`, `alvi`. El scraper intenta API VTEX clasica y tiene fallback defensivo por HTML embebido cuando el sitio no expone JSON directo. Jumbo usa `https://bff.jumbo.cl/catalog/plp`; Santa Isabel expone `https://bff.santaisabel.cl/catalog/plp` en navegador, pero puede responder 401 desde requests sin token/sesion. Alvi usa `https://bff-alvi-web.alvi.cl/categories/` y `https://bff-alvi-web.alvi.cl/products/intelligence-search-plp`.
- Walmart: `lider`, `acuenta`. Las categorias son curadas; productos requieren configurar `LIDER_API_TEMPLATE` / `ACUENTA_API_TEMPLATE` o `api_template` en `lider_scraper/lider_stores.py`.
- Falabella: `tottus`. Las categorias son curadas; productos requieren `TOTTUS_API_TEMPLATE` o `API_TEMPLATE_DEFAULT` en `tottus_scraper/tottus.py`. La PLP real vive en rutas tipo `https://www.tottus.cl/tottus-cl/lista/CATG27055/Despensa`; `www.tottus.cl` puede requerir Cloudflare challenge para requests directos.
- Si Walmart/Falabella o una tienda bloquea el endpoint, debe devolver `[]` con `meta["warning"]` sin romper la busqueda conjunta.

> Los archivos `server.py`, `server_http.py`, `run_dev.py` y carpetas `web/` dentro de cada scraper son **legado inactivo**. No borrarlos pero no depender de ellos.

---

## 11. Automatizacion

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

## 12. Despliegue y Produccion

El despliegue empaqueta la aplicacion de busqueda conjunta:

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

---

## 13. Datos, Salidas y Archivos Sensibles

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

## 14. Carpetas Auxiliares o de Referencia

Estas carpetas pueden servir como referencia, pero no son runtime principal:

- `_ref_mercadolibre_ui/`: referencia UI TypeScript/React.
- `_design_import/`: importacion/diseño experimental.
- `pro_descuento_mockup_figma/`: mockups/capturas.
- `presentacion_soluciones/`: material de presentacion.
- `scratch/`: scripts temporales de inspeccion.

No refactorizar ni borrar estas carpetas como parte de cambios funcionales salvo que la tarea lo pida.

---

## 15. Convenciones de Desarrollo para IA

Antes de cambiar codigo:

- Leer el archivo objetivo y los contratos cercanos.
- Buscar endpoints/funciones existentes con `rg`.
- Identificar si el cambio afecta la busqueda global/UI/automatizacion.

Python:

- Usar `.venv/` cuando exista.
- Agregar dependencias a `requirements.txt` correspondiente.
- Mantener scrapers desacoplados.
- Usar timeouts y headers realistas en scraping.
- No romper firmas usadas por `global_search.py`.
- Si una funcion devuelve items, preservar nombres de campos que la UI ya usa: `title`, `name`, `price`, `link`, `url`, `image`, `discount_percent`, `condition`, `store`, `category`, etc.

FastAPI:

- Mantener endpoints bajo `/api`.
- Mantener `GET /api/health`.
- Preservar CORS permisivo para desarrollo local salvo requerimiento explicito.
- Si se sirve SPA, montar assets y fallback a `index.html` solo cuando exista `dist`.

Frontend:

- Respetar proxy Vite (`/api` -> `127.0.0.1:8000`).
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

## 16. Checklist para Agregar una Nueva Fuente

1. Crear carpeta del scraper con modulo Python principal.
2. Definir una funcion reusable tipo `execute_search` o `collect_results`.
3. Normalizar resultados a diccionarios con campos comunes.
4. Agregar runner en `global_search.py`.
5. Agregar source a `DEFAULT_SOURCES` si debe participar por defecto.
6. Agregar controles/opciones en `web/src/global-search`.
7. Actualizar este `agents.md`.
8. Probar busqueda conjunta con la nueva fuente.

> Ya no se necesita crear `server.py` ni `web/` por fuente. Los scrapers se importan directamente como modulos Python.

---

## 17. Checklist para Agregar un Filtro Global

1. Agregar default y normalizacion en `global_search.build_config`.
2. Pasar el campo al runner de cada fuente que lo soporte.
3. Ajustar filtros transversales si aplica.
4. Agregar control en `GlobalSearchTerminal.jsx` o `GlobalSearchFilterModal.jsx`.
5. Mostrar resumen/estado si corresponde en HUD o resultados.
6. Mantener compatibilidad cuando el campo no venga desde clientes antiguos.
7. Probar busqueda rapida con 2 o 3 fuentes.

---

## 18. Pruebas y Verificacion Recomendada

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

Servicio completo:

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

## 19. Problemas Frecuentes

- **Puerto ocupado**: revisar puertos 8000 (API) y 5173 (web).
- **Vite sin dependencias**: ejecutar `npm ci` dentro de `web/` o dejar que `run_all.py` lo haga.
- **MercadoLibre devuelve shell/bloqueo**: usar `ML_COOKIE`, `cookies.txt` o `--cookie-file`.
- **Facebook no devuelve datos**: revisar cookies/perfil, ubicacion, radio y cambios del sitio.
- **Resultados irrelevantes**: revisar `include_words`, `exclude_words`, `strict_mode` y `smart_filter`.
- **Categoria "todas" en SoloTodo**: no reemplazar `0` por default; `global_search.py` tiene helpers para preservar ese valor.
- **Produccion no muestra UI**: verificar que `web/dist` exista y que Docker haya corrido `npm ci && npm run build`.
- **PcFactory devuelve pocos resultados o cantidades incorrectas**: revisar primero si el filtro inteligente global esta descartando accesorios o resultados con palabras ambiguas. El scraper actual consulta directamente la API de pcFactory y fuerza busqueda completa.
- **AliExpress bloqueado (403/captcha)**: AliExpress usa Akamai Bot Manager. No se puede scrapear con `requests` simple; requiere Playwright + stealth. Verificar que cookies regionales esten configuradas para Chile.

---

## 20. Principio de Mantenimiento

El proyecto crece por fuentes. Mantener cada scraper aislado como modulo Python, pero conectar solo lo necesario en estos puntos transversales:

- `global_search.py` para busqueda multiscraper.
- `server.py` para exponer la API de busqueda global.
- `web/src/global-search/` para la experiencia de usuario.
- `agents.md` para que futuras IA no tengan que redescubrir la arquitectura.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, invoke the `skill` tool with `skill: "graphify"` before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

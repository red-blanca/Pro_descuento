# Facebook Marketplace Export UI

Proyecto separado del flujo de Mercado Libre, enfocado en Facebook Marketplace.

Incluye:

- `facebook_marketplace.py`: scraper por navegador con Playwright
- `server.py`: API FastAPI para conteo, preview y export
- `web/`: frontend React
- `automation/`: base para corridas programadas

## Requisitos

- Python 3.10+
- Node.js LTS
- Chromium para Playwright

## Instalacion backend

```bash
cd facebook_marketplace
pip install -r requirements.txt
python -m playwright install chromium
```

## Levantar backend

```bash
cd facebook_marketplace
python -m uvicorn server:app --host 127.0.0.1 --port 8010
```

## Levantar frontend

```bash
cd facebook_marketplace/web
npm install
npm run dev
```

La UI quedara en `http://127.0.0.1:5184`.

## Un solo comando

```bash
cd facebook_marketplace
python run_dev.py
```

## Guardar sesion de Facebook

Si ya usas Facebook normalmente, igual necesitas una sesion exportada para que Playwright la reutilice.

Opcion recomendada si ya tienes Facebook abierto en tu navegador normal:

```bash
cd facebook_marketplace
python import_browser_cookies.py --browser chrome
```

Si usas Edge:

```bash
python import_browser_cookies.py --browser edge
```

Eso intenta leer solo las cookies de `facebook.com` desde tu navegador local y generar `storage_state.json`.

Si Chrome/Edge no dejan exportarlas, tambien puedes pegar manualmente tus cookies en:

```bash
facebook_marketplace/facebook_cookies.txt
```

Luego convertirlas con:

```bash
python import_cookie_text.py
```

Necesitas al menos:

- `c_user`
- `xs`

Si eso no funciona, usa el flujo manual:

```bash
cd facebook_marketplace
python login_facebook.py
```

Eso abre Chrome real con un perfil persistente en `facebook_marketplace/chrome_profile`. Inicias sesion si hace falta, completas cualquier verificacion si aparece, luego entras manualmente a Marketplace, vuelves a la terminal y presionas Enter. Se guardara:

```bash
facebook_marketplace/storage_state.json
```

Luego puedes usarlo asi:

```bash
python facebook_marketplace.py notebook gamer --user-data-dir chrome_profile --json
```

Tambien puedes seguir usando `storage_state.json` si el login manual logra exportarlo.

## Uso CLI

Busqueda simple:

```bash
cd facebook_marketplace
python facebook_marketplace.py notebook gamer --marketplace-path curico --limit 40 --show-browser
```

Salida JSON:

```bash
python facebook_marketplace.py notebook gamer --marketplace-path curico --json --show-browser
```

Exportar Excel:

```bash
python facebook_marketplace.py notebook gamer --location-query "Curico, Maule, Chile" --radius-km 12 --export-xlsx --show-browser
```

Usar URL exacta:

```bash
python facebook_marketplace.py --search-url "https://www.facebook.com/marketplace/curico/search?query=notebook" --json --show-browser
```

## Sesion autenticada

Facebook puede pedir login. La forma mas estable en este proyecto es usar un `storage state` de Playwright.

Tambien desde la UI:

- escribe la ruta en `Archivo storage state`
- o mejor: usa `Perfil persistente Chrome` con `chrome_profile`

## Ubicacion Chile + radio

El proyecto ahora soporta:

- `location_query`: ubicacion base, por defecto `Curico, Maule, Chile`
- `radius_km`: radio de busqueda, por defecto `12`
- `latitude` y `longitude`: opcion manual si quieres fijar coordenadas exactas
- `country_code`: por defecto `CL`

Ejemplo:

```bash
python facebook_marketplace.py notebook gamer --storage-state storage_state.json --location-query "Curico, Maule, Chile" --radius-km 12 --json
```

## Descripcion opcional

La descripcion completa no viene en el listado. Para traerla, el scraper entra a cada publicacion.

Eso sirve para:

- `preview`
- `export`

No se usa en `count`, para no volverlo lento.

CLI:

```bash
python facebook_marketplace.py notebook gamer --storage-state storage_state.json --include-description --json
```

UI:

- activa `Incluir descripcion`

## Endpoints API

- `POST /api/count-exact`
- `POST /api/preview`
- `POST /api/export`
- `GET /api/health`

## Notas

- Facebook Marketplace usa contenido dinamico, por eso este proyecto usa navegador real.
- La estructura se mantuvo parecida a la de Mercado Libre, pero el motor interno es distinto.
- Si Facebook devuelve login wall o cambia el DOM, habra que ajustar selectores.

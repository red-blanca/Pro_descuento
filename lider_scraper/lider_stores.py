from __future__ import annotations

"""Configuracion de las tiendas Walmart Chile (Lider y acuenta).

api_template: plantilla del endpoint JSON de catalogo. Soporta los campos
  {host} {category} {query} {limit} {page}. Dejalo vacio hasta confirmar el
  endpoint real (Paso 1) o sobreescribelo con la variable de entorno indicada
  en api_env.
"""

WALMART_STORES: dict[str, dict] = {
    "lider": {
        "source": "lider",
        "store_label": "Lider",
        "host": "https://www.lider.cl",
        "api_env": "LIDER_API_TEMPLATE",
        # Ejemplo (confirmar): "{host}/catalogo/api/v2/category/{category}?page={page}&limit={limit}"
        "api_template": "",
        "group": "Walmart",
    },
    "acuenta": {
        "source": "acuenta",
        "store_label": "acuenta",
        "host": "https://www.acuenta.cl",
        "api_env": "ACUENTA_API_TEMPLATE",
        "api_template": "",
        "group": "Walmart",
    },
}

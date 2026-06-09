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
        "browser_fetch": True,
        "categories": [
            ("frescos-y-lacteos/07", "Frescos y Lacteos"),
            ("carnes-y-pescados/03", "Carnes y Pescados"),
            ("despensa/05", "Despensa"),
            ("bebidas-y-snacks/02", "Bebidas y Snacks"),
            ("frutas-y-verduras/06", "Frutas y Verduras"),
            ("aseo-y-limpieza/11", "Aseo y Limpieza"),
            ("perfumeria-y-cuidado-personal/12", "Perfumeria y Cuidado Personal"),
            ("congelados/04", "Congelados"),
            ("desayuno-y-dulces/44", "Desayuno y Dulces"),
            ("panaderia-y-pasteleria/10", "Panaderia y Pasteleria"),
            ("mascotas/88", "Mascotas"),
            ("mundo-bebe/09", "Mundo Bebe"),
            ("el-bar/80", "El Bar"),
            ("hogar-entretencion-y-tecnologia/47", "Hogar, Entretencion y Tecnologia"),
        ],
        "group": "Walmart",
    },
}

from __future__ import annotations

"""
Configuracion por tienda VTEX.

- host: dominio base del supermercado.
- sales_channel: canal de venta VTEX. Vacio = canal por defecto (1).
    Algunas tiendas usan canales por region; si necesitas precios/stock de
    Curico, ajusta aqui el canal correspondiente (se descubre inspeccionando
    la cookie 'vtex_segment' o el parametro 'sc' en la web).
- tree_depth: profundidad del arbol de categorias a solicitar.

Todos estos supermercados corren sobre VTEX, por lo que comparten el mismo
motor (vtex_core).
"""

VTEX_STORES: dict[str, dict] = {
    "jumbo": {
        "source": "jumbo",
        "store_label": "Jumbo",
        "host": "https://www.jumbo.cl",
        "bff_plp_url": "https://bff.jumbo.cl/catalog/plp",
        "bff_store": "jumboclj512",
        "sales_channel": "",
        "tree_depth": 4,
        "group": "Cencosud",
        "categories": [
            ("frutas-y-verduras", "Frutas y Verduras"),
            ("lacteos-huevos-y-congelados", "Lacteos, Huevos y Congelados"),
            ("quesos-y-fiambres", "Quesos y Fiambres"),
            ("despensa", "Despensa"),
            ("carnes-y-pescados", "Carnes y Pescados"),
            ("panaderia-y-pasteleria", "Panaderia y Pasteleria"),
            ("licores-bebidas-y-aguas", "Licores, Bebidas y Aguas"),
            ("chocolates-galletas-y-snacks", "Chocolates, Galletas y Snacks"),
            ("limpieza", "Limpieza"),
            ("cuidado-personal-y-bebe", "Cuidado Personal y Bebe"),
            ("mascotas", "Mascotas"),
            ("hogar-jugueteria-y-libreria", "Hogar, Jugueteria y Libreria"),
            ("farmacia", "Farmacia"),
        ],
    },
    "santaisabel": {
        "source": "santaisabel",
        "store_label": "Santa Isabel",
        "host": "https://www.santaisabel.cl",
        "bff_plp_url": "https://bff.santaisabel.cl/catalog/plp",
        "bff_store": "pedrofontova",
        "bff_store_env": "SANTAISABEL_STORE",
        "bff_auth_header": "apikey",
        "bff_auth_env": "SANTAISABEL_BFF_AUTH",
        "sales_channel": "",
        "tree_depth": 4,
        "group": "Cencosud",
        "categories": [
            ("lacteos-huevos-y-congelados/leches/leche-liquida", "Lacteos / Leche Liquida"),
            ("botilleria/bebidas-gaseosas", "Bebidas"),
            ("lacteos-huevos-y-congelados/yoghurt", "Lacteos / Yoghurt"),
            ("carnes-y-pescados/vacuno", "Carnes / Vacuno"),
            ("chocolates-galletas-y-snacks", "Galletas"),
            ("frutas-y-verduras/frutas", "Frutas"),
            ("frutas-y-verduras/verduras", "Verduras"),
            ("botilleria/cervezas", "Cervezas"),
            ("despensa", "Despensa"),
            ("botilleria/vinos", "Vinos"),
        ],
    },
    "unimarc": {
        "source": "unimarc",
        "store_label": "Unimarc",
        "host": "https://www.unimarc.cl",
        "sales_channel": "",
        "tree_depth": 4,
        "group": "SMU",
    },
    "alvi": {
        "source": "alvi",
        "store_label": "Alvi",
        "host": "https://www.alvi.cl",
        "bff_categories_url": "https://bff-alvi-web.alvi.cl/categories/",
        "bff_products_url": "https://bff-alvi-web.alvi.cl/products/intelligence-search-plp",
        "bff_search_url": "https://bff-alvi-web.alvi.cl/products/intelligence-search/{query}/",
        "bff_by_category_url": "https://bff-alvi-web.alvi.cl/products/by-category/",
        "sales_channel": "",
        "tree_depth": 4,
        "group": "SMU",
    },
}

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
        "sales_channel": "",
        "tree_depth": 4,
        "group": "Cencosud",
    },
    "santaisabel": {
        "source": "santaisabel",
        "store_label": "Santa Isabel",
        "host": "https://www.santaisabel.cl",
        "sales_channel": "",
        "tree_depth": 4,
        "group": "Cencosud",
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
        "sales_channel": "",
        "tree_depth": 4,
        "group": "SMU",
    },
}

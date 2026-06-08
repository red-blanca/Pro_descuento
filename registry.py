from __future__ import annotations

"""Registro central de fuentes de supermercado.

Mapea el nombre de la fuente (source) al modulo scraper correspondiente.
Util tanto para el demo CLI como referencia para integrar en global_search.py.

Requiere que los directorios vtex_scraper/, lider_scraper/ y tottus_scraper/
esten en sys.path (el demo y global_search.py ya lo hacen).
"""

import importlib
from types import ModuleType

# source -> nombre de modulo importable
SUPERMARKET_SOURCES: dict[str, str] = {
    "jumbo": "jumbo",
    "santaisabel": "santaisabel",
    "unimarc": "unimarc",
    "alvi": "alvi",
    "lider": "lider",
    "acuenta": "acuenta",
    "tottus": "tottus",
}

_CACHE: dict[str, ModuleType] = {}


def get_module(source: str) -> ModuleType:
    source = source.strip().lower()
    if source not in SUPERMARKET_SOURCES:
        raise KeyError(f"Fuente de supermercado desconocida: {source}")
    if source not in _CACHE:
        _CACHE[source] = importlib.import_module(SUPERMARKET_SOURCES[source])
    return _CACHE[source]


def all_sources() -> list[str]:
    return list(SUPERMARKET_SOURCES.keys())


# ---------------------------------------------------------------------------
# Grupo "Supermercados" para la UI (vista separada, funcionalidad unificada).
# El front usa esta lista para armar la pestana/seccion de Supermercados y
# enviar estas fuentes al MISMO endpoint /api/global-search del proyecto.
# ---------------------------------------------------------------------------

SUPERMARKET_SOURCE_IDS: list[str] = [
    "jumbo",
    "santaisabel",
    "unimarc",
    "alvi",
    "lider",
    "acuenta",
    "tottus",
]

# Metadatos de presentacion (label visible + plataforma) para el front.
SUPERMARKET_META: dict[str, dict[str, str]] = {
    "jumbo": {"label": "Jumbo", "platform": "vtex"},
    "santaisabel": {"label": "Santa Isabel", "platform": "vtex"},
    "unimarc": {"label": "Unimarc", "platform": "vtex"},
    "alvi": {"label": "Alvi", "platform": "vtex"},
    "lider": {"label": "Lider", "platform": "walmart"},
    "acuenta": {"label": "acuenta", "platform": "walmart"},
    "tottus": {"label": "Tottus", "platform": "falabella"},
}


def is_supermarket_source(source: str) -> bool:
    """True si la fuente pertenece al grupo de supermercados."""
    return (source or "").strip().lower() in SUPERMARKET_SOURCES

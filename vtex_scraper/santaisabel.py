from __future__ import annotations

"""Scraper de Santa Isabel (Cencosud, plataforma VTEX). Extraccion por categoria."""

from typing import Any

import vtex_core
from stores import VTEX_STORES

STORE = VTEX_STORES["santaisabel"]
SOURCE = STORE["source"]


def fetch_categories() -> list[dict[str, Any]]:
    return vtex_core.fetch_categories(STORE)


def collect_results(
    query: str = "",
    limit: int = 80,
    scan_scope: str = "complete",
    max_pages: int = 0,
    **kwargs: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return vtex_core.collect_results(
        STORE,
        query=query,
        limit=limit,
        scan_scope=scan_scope,
        max_pages=max_pages,
        **kwargs,
    )


def apply_filters(items: list[dict[str, Any]], **kwargs: Any) -> list[dict[str, Any]]:
    return vtex_core.apply_filters(items, **kwargs)

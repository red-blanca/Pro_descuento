from __future__ import annotations

"""Scraper de acuenta (Walmart Chile). Extraccion por categoria."""

from typing import Any

import lider_core
from lider_stores import WALMART_STORES

STORE = WALMART_STORES["acuenta"]
SOURCE = STORE["source"]


def fetch_categories() -> list[dict[str, Any]]:
    return lider_core.fetch_categories(STORE)


def collect_results(
    query: str = "",
    limit: int = 80,
    scan_scope: str = "complete",
    max_pages: int = 0,
    **kwargs: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return lider_core.collect_results(
        STORE,
        query=query,
        limit=limit,
        scan_scope=scan_scope,
        max_pages=max_pages,
        **kwargs,
    )


def apply_filters(items: list[dict[str, Any]], **kwargs: Any) -> list[dict[str, Any]]:
    return lider_core.apply_filters(items, **kwargs)

"""Sugerencia conservadora de categorías para búsqueda global (términos generales)."""
from __future__ import annotations

import re
import unicodedata
from typing import Any


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    cleaned = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", cleaned.lower().strip())


def _tokens(query: str) -> list[str]:
    return [t for t in _normalize(query).split() if len(t) >= 2]


def _score_label(query: str, label: str) -> float:
    q = _normalize(query)
    if not q:
        return 0.0
    label_n = _normalize(label)
    if not label_n:
        return 0.0
    if q in label_n or label_n in q:
        return 1.0
    q_tokens = _tokens(q)
    if not q_tokens:
        return 0.0
    label_tokens = set(_tokens(label_n))
    overlap = sum(1 for t in q_tokens if t in label_n or any(t in lt for lt in label_tokens))
    return overlap / len(q_tokens)


def _label_for_value(categories: list[dict[str, Any]], value: Any) -> str:
    if value is None or value == "" or value == 0:
        return "Todas"
    for cat in categories:
        cv = cat.get("value")
        if str(cv) == str(value) or cv == value:
            return str(cat.get("label") or cat.get("name") or cat.get("path") or value)
    return str(value)


# Términos generales -> categoría amplia Pulga
_PULGA_HINTS: list[tuple[tuple[str, ...], str]] = [
    (("notebook", "laptop", "computador", "computadora", "macbook", "pc", "ultrabook"), "tecnologia"),
    (("celular", "celulares", "iphone", "samsung", "xiaomi", "telefono", "smartphone", "movil"), "tecnologia"),
    (("audifono", "audifonos", "auricular", "auriculares", "airpod", "headphone", "earbud"), "tecnologia"),
    (("tv", "televisor", "televisores", "monitor", "pantalla", "smart tv"), "tecnologia"),
    (("tablet", "ipad", "consola", "playstation", "xbox", "nintendo", "switch"), "tecnologia"),
    (("camara", "camera", "drone"), "tecnologia"),
    (("impresora", "router", "modem", "teclado", "mouse", "ssd", "ram", "disco"), "tecnologia"),
    (("zapatilla", "zapatillas", "zapato", "ropa", "polera", "pantalon"), "moda"),
    (("bicicleta", "bici", "mtb"), "bicicletas"),
    (("deporte", "gym", "fitness", "pesas"), "deporte"),
    (("mueble", "sillon", "mesa", "silla", "hogar"), "hogar"),
    (("refrigerador", "lavadora", "microondas", "horno", "electrodomestico"), "electrodomesticos"),
    (("juguete", "bebe", "nino"), "bebes"),
]


def suggest_pulga(query: str, categories: list[dict[str, Any]] | None = None) -> str:
    q = _normalize(query)
    if not q:
        return ""
    valid = {str(c.get("value") or "") for c in (categories or []) if str(c.get("value") or "")}
    for terms, slug in _PULGA_HINTS:
        if any(term in q for term in terms):
            if not valid or slug in valid:
                return slug
    techish = ("tech", "gamer", "gaming", "digital", "electron")
    if any(t in q for t in techish) and (not valid or "tecnologia" in valid):
        return "tecnologia"
    return ""


def suggest_from_counts(
    query: str,
    categories: list[dict[str, Any]],
    *,
    min_ratio: float = 1.8,
    min_label_score: float = 0.34,
) -> str:
    """Elige categoría dominante por volumen; si hay empate, devuelve Todas ('')."""
    q = _normalize(query)
    if not q:
        return ""

    valid = [c for c in categories if str(c.get("value") or c.get("id") or "").strip()]
    if not valid:
        return ""

    with_count = [c for c in valid if int(c.get("count") or 0) > 0]
    pool = with_count if with_count else valid

    def sort_key(item: dict[str, Any]) -> tuple[float, float, str]:
        count = int(item.get("count") or 0)
        label = str(item.get("label") or item.get("name") or item.get("path") or "")
        return (count, _score_label(q, label), label)

    ranked = sorted(pool, key=sort_key, reverse=True)
    top = ranked[0]
    top_value = str(top.get("value") or top.get("id") or "")
    top_count = int(top.get("count") or 0)
    second_count = int(ranked[1].get("count") or 0) if len(ranked) > 1 else 0
    top_label = str(top.get("label") or top.get("name") or top.get("path") or "")
    label_score = _score_label(q, top_label)

    if len(ranked) == 1:
        return top_value if label_score >= min_label_score or top_count > 0 else ""

    if top_count > 0 and (second_count == 0 or top_count >= second_count * min_ratio):
        return top_value

    if label_score >= 0.66:
        return top_value

    return ""


def suggest_by_label(
    query: str,
    categories: list[dict[str, Any]],
    *,
    min_score: float = 0.5,
    prefer_shallow: bool = True,
) -> str | int:
    q = _normalize(query)
    if not q or not categories:
        return ""

    best: tuple[float, int, Any] | None = None
    for cat in categories:
        value = cat.get("value")
        if value is None or value == "" or value == 0:
            continue
        label = str(cat.get("label") or cat.get("name") or cat.get("path") or "")
        score = _score_label(q, label)
        if score < min_score:
            continue
        depth = int(cat.get("depth") or 0)
        depth_key = depth if prefer_shallow else -depth
        candidate = (score, -depth_key, value)
        if best is None or candidate > best:
            best = candidate
    return best[2] if best else ""


def build_suggestions(
    query: str,
    categories: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    q = query.strip()
    pulga = categories.get("pulga") or []
    knasta = categories.get("knasta") or []
    solotodo = categories.get("solotodo") or []
    travel = categories.get("travel") or []
    tuganga = categories.get("tuganga") or []

    pulga_cat = suggest_pulga(q, pulga) if q else ""
    knasta_cat = suggest_from_counts(q, knasta) if q else ""
    tuganga_cat = suggest_from_counts(q, tuganga) if q else ""

    solotodo_id: int | str = 0
    solo = suggest_by_label(q, solotodo, min_score=0.45, prefer_shallow=True)
    if solo:
        solotodo_id = int(solo) if str(solo).isdigit() else solo

    travel_id = ""
    travel_pick = suggest_by_label(q, travel, min_score=0.42, prefer_shallow=True)
    if travel_pick:
        travel_id = str(travel_pick)

    labels = {
        "pulga": _label_for_value(pulga, pulga_cat),
        "knasta": _label_for_value(knasta, knasta_cat),
        "solotodo": _label_for_value(solotodo, solotodo_id),
        "travel": _label_for_value(travel, travel_id),
        "tuganga": _label_for_value(tuganga, tuganga_cat),
    }

    return {
        "pulga_category": pulga_cat,
        "knasta_category": knasta_cat,
        "solotodo_category_id": solotodo_id,
        "travel_category_id": travel_id,
        "tuganga_category": tuganga_cat,
        "tuganga_mode": "search" if q else None,
        "labels": labels,
    }

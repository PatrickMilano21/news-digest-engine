# src/normalize.py
from __future__ import annotations

from src.schemas import NewsItem, dedupe_key


def normalize_and_dedupe(items: list[NewsItem]) -> list[NewsItem]:
    seen: set[str] = set()
    out: list[NewsItem] = []

    for item in items:
        key = dedupe_key(str(item.url), item.title)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)

    return out

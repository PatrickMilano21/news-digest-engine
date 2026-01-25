"""
View/presentation helpers for building display objects.

This module handles transforming data into view models for templates.
Separates display logic from routes so UI changes don't require editing main.py.
"""
from __future__ import annotations

import json
from datetime import datetime

from src.scoring import RankConfig, score_item
from src.explain import explain_item
from src.cache_utils import compute_cache_key
from src.clients.llm_openai import MODEL
from src.repo import get_cached_summary
from src.llm_schemas.summary import SummaryResult
from src.schemas import NewsItem


def build_ranked_display_items(
    conn,
    items_with_ids: list[tuple[int, NewsItem]],
    now: datetime,
    cfg: RankConfig,
    top_n: int,
) -> list[dict]:
    """
    Score, rank, and build display objects with explanations and summaries.

    Args:
        conn: Database connection
        items_with_ids: List of (db_id, NewsItem) tuples
        now: Reference time for scoring
        cfg: Ranking configuration
        top_n: Number of items to return

    Returns:
        List of display dicts with keys: id, item, score, expl, summary
    """
    # Score each item
    scored_pairs = []
    for idx, (db_id, item) in enumerate(items_with_ids):
        score = score_item(item, now=now, cfg=cfg)
        scored_pairs.append((score, item.published_at, idx, db_id, item))

    # Sort by score desc, published_at desc, index asc
    scored_pairs.sort(key=lambda t: (-t[0], -t[1].timestamp(), t[2]))

    # Build display objects for top N
    display_items = []
    for score, _, _, db_id, item in scored_pairs[:top_n]:
        expl = explain_item(item, now=now, cfg=cfg)
        summary = _fetch_cached_summary(conn, item)

        display_items.append({
            "id": db_id,
            "item": item,
            "score": score,
            "expl": expl,
            "summary": summary,
        })

    return display_items


def _fetch_cached_summary(conn, item: NewsItem) -> SummaryResult | None:
    """Fetch cached LLM summary for an item, if available."""
    evidence = item.evidence or ""
    if not evidence:
        return None

    cache_key = compute_cache_key(MODEL, evidence)
    cached = get_cached_summary(conn, cache_key=cache_key)

    if not cached:
        return None

    try:
        return SummaryResult(**json.loads(cached["summary_json"]))
    except Exception:
        return None

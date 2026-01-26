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
from src.repo import (
    get_cached_summary,
    get_distinct_dates,
    count_distinct_dates,
    get_run_by_day,
    get_run_feedback,
    get_recent_runs_summary,
    count_items_for_dates,
    count_runs_for_dates,
    get_items_count_by_date,
)
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


def build_homepage_data(conn, *, page: int = 1, per_page: int = 10) -> dict:
    """Build data for the homepage view.

    Composes repo primitives to build the homepage display model.

    Returns:
        {
            "dates": [{"day": "2026-01-25", "run_id": "abc", "rating": 4}, ...],
            "runs": [{"run_id": "...", "day": "...", "status": "ok", ...}, ...],
            "pagination": {"page": 1, "per_page": 10, "total": 45, "total_pages": 5,
                           "has_prev": False, "has_next": True}
        }
    """
    # Get total and paginated dates
    total = count_distinct_dates(conn)
    offset = (page - 1) * per_page
    dates = get_distinct_dates(conn, limit=per_page, offset=offset)

    # Enrich each date with run_id and rating
    dates_with_stats = []
    for day in dates:
        run = get_run_by_day(conn, day=day)
        run_id = run["run_id"] if run else None
        rating = 0
        if run_id:
            feedback = get_run_feedback(conn, run_id=run_id)
            rating = feedback["rating"] if feedback else 0
        dates_with_stats.append({"day": day, "run_id": run_id, "rating": rating})

    # Get recent runs
    runs = get_recent_runs_summary(conn, limit=10)

    # Pagination
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1

    return {
        "dates": dates_with_stats,
        "runs": runs,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
        }
    }


def build_debug_stats(conn, *, date_limit: int = 10) -> dict:
    """Build data for the /debug/stats endpoint.

    Composes repo primitives to build debug statistics.

    Returns:
        {
            "items_count": 1234,
            "runs_count": 45,
            "items_by_date": [{"date": "2026-01-25", "items": 150}, ...],
            "recent_runs": [{"run_id": "...", ...}, ...]
        }
    """
    # Get last N dates
    dates = get_distinct_dates(conn, limit=date_limit)

    # Counts scoped to those dates
    items_count = count_items_for_dates(conn, dates=dates)
    runs_count = count_runs_for_dates(conn, dates=dates)

    # Breakdown by date
    items_by_date = get_items_count_by_date(conn, dates=dates)

    # Recent runs
    recent_runs = get_recent_runs_summary(conn, limit=10)

    return {
        "items_count": items_count,
        "runs_count": runs_count,
        "items_by_date": items_by_date,
        "recent_runs": recent_runs,
    }

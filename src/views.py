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
    get_cached_tags,
    set_cached_tags,
    get_distinct_dates,
    count_distinct_dates,
    get_run_by_day,
    get_run_feedback,
    get_recent_runs_summary,
    count_items_for_dates,
    count_runs_for_dates,
    get_items_count_by_date,
    get_user_config,
    get_active_source_weights,
)
from src.llm_schemas.summary import SummaryResult
from src.schemas import NewsItem
from src.clients.llm_openai import suggest_feedback_tags


def build_ranked_display_items(
    conn,
    items_with_ids: list[tuple[int, NewsItem]],
    now: datetime,
    cfg: RankConfig,
    top_n: int,
    ai_scores: dict[str, float] | None = None,
) -> list[dict]:
    """
    Score, rank, and build display objects with explanations and summaries.

    Args:
        conn: Database connection
        items_with_ids: List of (db_id, NewsItem) tuples
        now: Reference time for scoring
        cfg: Ranking configuration
        top_n: Number of items to return
        ai_scores: Optional url -> ai_score mapping (Milestone 3c)

    Returns:
        List of display dicts with keys: id, item, score, expl, summary
    """
    # Score each item (base_score + ai_score boost)
    scored_pairs = []
    for idx, (db_id, item) in enumerate(items_with_ids):
        base_score = score_item(item, now=now, cfg=cfg)
        item_ai_score = ai_scores.get(str(item.url), 0.0) if ai_scores else 0.0
        final_score = base_score + (cfg.ai_score_alpha * item_ai_score)
        scored_pairs.append((final_score, item.published_at, idx, db_id, item))

    # Sort by score desc, published_at desc, index asc
    scored_pairs.sort(key=lambda t: (-t[0], -t[1].timestamp(), t[2]))

    # Build display objects for top N
    display_items = []
    for score, _, _, db_id, item in scored_pairs[:top_n]:
        expl = explain_item(item, now=now, cfg=cfg)
        summary = _fetch_cached_summary(conn, item)

        # Fetch or generate feedback tags (on-demand + cached)
        feedback_tags = _fetch_or_generate_tags(conn, db_id, item)

        display_items.append({
            "id": db_id,
            "item": item,
            "score": score,
            "expl": expl,
            "summary": summary,
            "feedback_tags": feedback_tags,
        })

    return display_items


def _fetch_or_generate_tags(conn, item_id: int, item: NewsItem) -> list[str]:
    """Fetch cached feedback tags or generate new ones via LLM.

    Uses hybrid approach: on-demand generation + cache in news_items.suggested_tags.
    Falls back to ["Other"] if LLM fails.
    """
    # Check cache first
    cached = get_cached_tags(conn, item_id=item_id)
    if cached is not None:
        return cached

    # Generate via LLM (exempt from daily cap per design)
    tags = suggest_feedback_tags(item)

    # Cache for future use
    set_cached_tags(conn, item_id=item_id, tags=tags)

    return tags


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


def build_homepage_data(
    conn,
    *,
    page: int = 1,
    per_page: int = 10,
    user_id: str | None = None,
) -> dict:
    """Build data for the homepage view.

    Composes repo primitives to build the homepage display model.

    Args:
        page: Page number (1-indexed)
        per_page: Items per page
        user_id: User ID for scoped data. None = global/legacy data.

    Returns:
        {
            "dates": [{"day": "2026-01-25", "run_id": "abc", "rating": 4}, ...],
            "runs": [{"run_id": "...", "day": "...", "status": "ok", ...}, ...],
            "pagination": {"page": 1, "per_page": 10, "total": 45, "total_pages": 5,
                           "has_prev": False, "has_next": True}
        }
    """
    # Get total and paginated dates (news_items are global/shared)
    total = count_distinct_dates(conn)
    offset = (page - 1) * per_page
    dates = get_distinct_dates(conn, limit=per_page, offset=offset)

    # Enrich each date with run_id and rating (user-scoped)
    dates_with_stats = []
    for day in dates:
        run = get_run_by_day(conn, day=day, user_id=user_id)
        run_id = run["run_id"] if run else None
        rating = 0
        if run_id:
            feedback = get_run_feedback(conn, run_id=run_id, user_id=user_id)
            rating = feedback["rating"] if feedback else 0
        dates_with_stats.append({"day": day, "run_id": run_id, "rating": rating})

    # Get recent runs (user-scoped)
    runs = get_recent_runs_summary(conn, limit=10, user_id=user_id)

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


def get_effective_rank_config(conn, *, user_id: str | None = None) -> RankConfig:
    """
    Build effective RankConfig for a user.

    Merges configuration in order:
    1. Start with defaults
    2. Overlay user_config (if exists)
    3. Overlay active source weights (user-scoped in future)

    Enforces bounds: ai_score_alpha clamped to [0.0, 0.2]

    Args:
        conn: Database connection
        user_id: User ID (None for global/legacy config)

    Returns:
        RankConfig with all overrides applied
    """
    # Start with defaults
    cfg_dict = RankConfig().model_dump()

    # Overlay user config if provided
    if user_id:
        user_config = get_user_config(conn, user_id=user_id)
        if user_config:
            # Merge user overrides (only specified fields)
            for key, value in user_config.items():
                if key in cfg_dict and value is not None:
                    cfg_dict[key] = value

    # Overlay active source weights (user-scoped)
    source_weights = get_active_source_weights(conn, user_id=user_id)
    cfg_dict["source_weights"] = source_weights

    # Enforce bounds on ai_score_alpha
    cfg_dict["ai_score_alpha"] = max(0.0, min(0.2, cfg_dict.get("ai_score_alpha", 0.1)))

    return RankConfig(**cfg_dict)

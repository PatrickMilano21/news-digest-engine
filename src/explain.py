from __future__ import annotations

from datetime import datetime
from src.schemas import NewsItem
from src.scoring import RankConfig, compute_score_breakdown


def explain_item(item: NewsItem, *, now: datetime, cfg: RankConfig) -> dict:
    """Return a dict explaining all score components for an item."""
    breakdown = compute_score_breakdown(item, now=now, cfg=cfg)
    return {
        "matched_topics": breakdown.matched_topics,
        "matched_keywords": breakdown.matched_keywords,
        "source_weight": breakdown.source_weight,
        "age_hours": round(breakdown.age_hours, 2),
        "recency_decay": round(breakdown.recency_decay, 4),
        "relevance": round(breakdown.relevance, 2),
        "total_score": round(breakdown.total_score, 4),
    }

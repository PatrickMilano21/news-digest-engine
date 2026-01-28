from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from src.schemas import NewsItem


class RankConfig(BaseModel):
    # Default topics for tech news - matches add +1.0 to relevance
    topics: list[str] = Field(default_factory=lambda: [
        "AI", "artificial intelligence", "machine learning",
        "startup", "funding", "raised",
        "cloud", "AWS", "Azure", "Google Cloud",
        "security", "cybersecurity", "breach",
        "open source", "GitHub",
    ])
    # Keyword boosts - specific high-signal words
    keyword_boosts: dict[str, float] = Field(default_factory=lambda: {
        "million": 0.5,
        "billion": 0.5,
        "acquisition": 0.5,
        "acquired": 0.5,
        "breakthrough": 0.5,
        "launches": 0.3,
        "announces": 0.3,
    })
    # Source weights - trusted sources get boost
    source_weights: dict[str, float] = Field(default_factory=lambda: {
        "techcrunch": 1.2,
        "hackernews": 1.1,
        "arstechnica": 1.1,
        "theverge": 1.0,
        "wired": 1.0,
    })
    search_fields: list[str] = Field(default_factory=lambda: ["title", "evidence"])
    recency_half_life_hours: float = 24.0 


def build_search_text(item: NewsItem, cfg: RankConfig) -> str:
    parts: list[str] = []
    if "title" in cfg.search_fields:
        parts.append(item.title or "")

    if "evidence" in cfg.search_fields:
        parts.append(item.evidence or "")

    return " ".join(parts).lower()


@dataclass
class ScoreBreakdown:
    """All components of a score calculation, for both scoring and explainability."""
    matched_topics: list[str] = field(default_factory=list)
    matched_keywords: list[dict] = field(default_factory=list)
    source_weight: float = 1.0
    age_hours: float = 0.0
    recency_decay: float = 1.0
    relevance: float = 0.0
    total_score: float = 0.0


def compute_score_breakdown(item: NewsItem, *, now: datetime, cfg: RankConfig) -> ScoreBreakdown:
    """Compute all score components for an item. Used by both score_item and explain_item."""
    # Recency calculation
    age_seconds = (now - item.published_at).total_seconds()
    age_hours = age_seconds / 3600.0
    if age_hours < 0.0:
        age_hours = 0.0

    half_life = cfg.recency_half_life_hours
    if half_life <= 0.0:
        half_life = 24.0

    recency_decay = 1.0 / (1.0 + (age_hours / half_life))

    # Topic and keyword matching
    text = build_search_text(item, cfg)
    matched_topics: list[str] = []
    for topic in cfg.topics:
        t = topic.strip().lower()
        if t and t in text:
            matched_topics.append(topic)

    matched_keywords: list[dict] = []
    for kw, boost in cfg.keyword_boosts.items():
        k = kw.strip().lower()
        if k and k in text:
            matched_keywords.append({"keyword": kw, "boost": float(boost)})

    # Source weight
    source_weight = float(cfg.source_weights.get(item.source.lower(), 1.0))

    # Calculate relevance and total score
    relevance = len(matched_topics) + sum(kw["boost"] for kw in matched_keywords)
    total_score = (1.0 + relevance) * source_weight * recency_decay

    return ScoreBreakdown(
        matched_topics=matched_topics,
        matched_keywords=matched_keywords,
        source_weight=source_weight,
        age_hours=age_hours,
        recency_decay=recency_decay,
        relevance=relevance,
        total_score=total_score,
    )


def score_item(item: NewsItem, *, now: datetime, cfg: RankConfig) -> float:
    """Return the total score for a single item."""
    breakdown = compute_score_breakdown(item, now=now, cfg=cfg)
    return breakdown.total_score


def rank_items(items: list[NewsItem], *, now: datetime, top_n: int, cfg: RankConfig) -> list[NewsItem]:
    scored: list[tuple[float, datetime, int, NewsItem]] = []
    for idx, it in enumerate(items):
        s = score_item(it, now=now, cfg=cfg)
        scored.append((s, it.published_at, idx, it))
    
    scored_sorted = sorted(
        scored, key=lambda t: (-t[0], -t[1].timestamp(), t[2]),
    )
    return [t[3] for t in scored_sorted[:top_n]]
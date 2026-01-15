from __future__ import annotations
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from src.schemas import NewsItem


class RankConfig(BaseModel):
    topics: list[str] = Field(default_factory=list)
    keyword_boosts: dict[str,float] = Field(default_factory=dict)
    source_weights: dict[str, float] = Field(default_factory=dict)
    search_fields: list[str] = Field(default_factory=lambda: ["title", "evidence"])
    recency_half_life_hours: float = 24.0 


def build_search_text(item: NewsItem, cfg: RankConfig) -> str:
    parts: list[str] = []
    if "title" in cfg.search_fields:
        parts.append(item.title or "")
    
    if "evidence" in cfg.search_fields:
        parts.append(item.evidence or "")
    
    return " ".join(parts).lower()
    

def score_item(item: NewsItem, *, now: datetime, cfg: RankConfig) -> float:
    age_seconds = (now - item.published_at).total_seconds()
    age_hours = age_seconds / 3600.0
    if age_hours < 0.0:
        age_hours = 0.0
    
    half_life = cfg.recency_half_life_hours
    if half_life <= 0.0:
        half_life = 24.0
    
    recency_decay = 1.0 / (1.0 + (age_hours /half_life))

    text = build_search_text(item, cfg)
    relevance = 0.0
    for topic in cfg.topics:
        t = topic.strip().lower()
        if t and t in text:
            relevance += 1.0
    
    for kw, boost in cfg.keyword_boosts.items():
        k = kw.strip().lower()
        if k and k in text:
            relevance += float(boost)
    
    source_w = cfg.source_weights.get(item.source.lower(), 1.0)

    base = relevance*float(source_w)
    return base * recency_decay


def rank_items(items: list[NewsItem], *, now: datetime, top_n: int, cfg: RankConfig) -> list[NewsItem]:
    scored: list[tuple[float, datetime, int, NewsItem]] = []
    for idx, it in enumerate(items):
        s = score_item(it, now=now, cfg=cfg)
        scored.append((s, it.published_at, idx, it))
    
    scored_sorted = sorted(
        scored, key=lambda t: (-t[0], -t[1].timestamp(), t[2]),
    )
    return [t[3] for t in scored_sorted[:top_n]]
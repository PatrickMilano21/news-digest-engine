from __future__ import annotations

from datetime import datetime
from src.schemas import NewsItem
from src.scoring import RankConfig, build_search_text


def explain_item(item: NewsItem, *, now: datetime, cfg: RankConfig) -> dict:
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

    age_seconds = (now - item.published_at).total_seconds()
    age_hours = age_seconds / 3600.0
    if age_hours < 0.0:
        age_hours = 0.0
    half_life = cfg.recency_half_life_hours
    if half_life <= 0.0:
        half_life = 24.0
    
    recency_decay = 1.0 / (1.0 + (age_hours / half_life))

    source_key = item.source.lower()
    source_weight = float(cfg.source_weights.get(source_key, 1.0))

    return {
        "matched_topics": matched_topics,
        "matched_keywords": matched_keywords,
        "source_weight": source_weight,
        "age_hours": round(age_hours, 2),
        "recency_decay": round(recency_decay,4),
    }

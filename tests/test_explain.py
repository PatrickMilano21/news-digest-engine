# tests/test_explain.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.explain import explain_item
from src.scoring import RankConfig
from src.schemas import NewsItem


def test_explain_matches_topics_and_keywords_case_insensitive_and_shapes():
    cfg = RankConfig(
        topics=["AI"],
        keyword_boosts={"merger": 5.0},
        source_weights={},
        search_fields=["title", "evidence"],
        recency_half_life_hours=24.0,
    )
    now = datetime(2026, 1, 14, 23, 59, 59, tzinfo=timezone.utc)

    item = NewsItem(
        source="reuters",
        url="https://example.com/a",
        published_at=now - timedelta(hours=10),
        title="nvidia in ai chip talks",
        evidence="Rumors of a MERGER are spreading",
    )

    expl = explain_item(item, now=now, cfg=cfg)

    assert "AI" in expl["matched_topics"]
    assert isinstance(expl["matched_keywords"], list)
    assert expl["matched_keywords"]  # at least one match

    first = expl["matched_keywords"][0]
    assert isinstance(first, dict)
    assert set(first.keys()) >= {"keyword", "boost"}
    assert first["keyword"] == "merger"
    assert first["boost"] == 5.0


def test_explain_source_weight_is_case_insensitive():
    cfg = RankConfig(
        topics=[],
        keyword_boosts={},
        source_weights={"reuters": 1.2},
        search_fields=["title", "evidence"],
        recency_half_life_hours=24.0,
    )
    now = datetime(2026, 1, 14, 23, 59, 59, tzinfo=timezone.utc)

    item = NewsItem(
        source="Reuters",  # mixed case on purpose
        url="https://example.com/a",
        published_at=now - timedelta(hours=1),
        title="Something happened",
        evidence="",
    )

    expl = explain_item(item, now=now, cfg=cfg)
    assert expl["source_weight"] == 1.2


def test_explain_negative_age_clamps_to_zero():
    cfg = RankConfig(
        topics=[],
        keyword_boosts={},
        source_weights={},
        search_fields=["title", "evidence"],
        recency_half_life_hours=24.0,
    )
    now = datetime(2026, 1, 14, 23, 59, 59, tzinfo=timezone.utc)

    item = NewsItem(
        source="reuters",
        url="https://example.com/a",
        published_at=now + timedelta(hours=2),  # future relative to now
        title="Future news",
        evidence="",
    )

    expl = explain_item(item, now=now, cfg=cfg)
    assert expl["age_hours"] == 0.0
    assert expl["recency_decay"] == 1.0


def test_explain_half_life_leq_zero_defaults_to_24h():
    cfg = RankConfig(
        topics=[],
        keyword_boosts={},
        source_weights={},
        search_fields=["title", "evidence"],
        recency_half_life_hours=0.0,  # should default to 24.0 inside explain
    )
    now = datetime(2026, 1, 14, 23, 59, 59, tzinfo=timezone.utc)

    # Age = 24h => decay = 1 / (1 + 24/24) = 0.5
    item = NewsItem(
        source="reuters",
        url="https://example.com/a",
        published_at=now - timedelta(hours=24),
        title="Old news",
        evidence="",
    )

    expl = explain_item(item, now=now, cfg=cfg)
    assert expl["recency_decay"] == 0.5

from datetime import datetime, timezone, timedelta

from src.schemas import NewsItem
from src.scoring import RankConfig, score_item, rank_items


def test_relevance_beats_recency():
    now = datetime(2026, 1, 13, 12, 0, 0, tzinfo=timezone.utc)
    cfg = RankConfig(
        topics=[],
        keyword_boosts={"merger": 5.0},
        source_weights={},
        search_fields=["title"],
        recency_half_life_hours=24.0,
    )

    newer = NewsItem(
        source="blog",
        url="https://a.com/1",
        published_at=now - timedelta(hours=1),
        title="Daily market wrap",
        evidence="",
    )
    older_relevant = NewsItem(
        source="blog",
        url="https://a.com/2",
        published_at=now - timedelta(hours=10),
        title="Company announces merger",
        evidence="",
    )

    assert score_item(older_relevant, now=now, cfg=cfg) > score_item(newer, now=now, cfg=cfg)


def test_keyword_match_in_evidence_counts():
    now = datetime(2026, 1, 13, 12, 0, 0, tzinfo=timezone.utc)
    cfg = RankConfig(
        topics=[],
        keyword_boosts={"earnings": 3.0},
        source_weights={},
        search_fields=["evidence"],
        recency_half_life_hours=24.0,
    )

    a = NewsItem(
        source="blog",
        url="https://a.com/1",
        published_at=now - timedelta(hours=2),
        title="Update",
        evidence="Company reports earnings beat",
    )
    b = NewsItem(
        source="blog",
        url="https://a.com/2",
        published_at=now - timedelta(hours=2),
        title="Update",
        evidence="Nothing important",
    )

    assert score_item(a, now=now, cfg=cfg) > score_item(b, now=now, cfg=cfg)


def test_source_weight_changes_ordering():
    now = datetime(2026, 1, 13, 12, 0, 0, tzinfo=timezone.utc)
    cfg = RankConfig(
        topics=["ai"],
        keyword_boosts={},
        source_weights={"tier1": 2.0, "tier3": 1.0},
        search_fields=["title"],
        recency_half_life_hours=24.0,
    )

    hi = NewsItem(
        source="tier1",
        url="https://a.com/1",
        published_at=now - timedelta(hours=3),
        title="AI update",
        evidence="",
    )
    lo = NewsItem(
        source="tier3",
        url="https://a.com/2",
        published_at=now - timedelta(hours=3),
        title="AI update",
        evidence="",
    )

    assert score_item(hi, now=now, cfg=cfg) > score_item(lo, now=now, cfg=cfg)


def test_stable_tie_preserves_input_order():
    now = datetime(2026, 1, 13, 12, 0, 0, tzinfo=timezone.utc)
    cfg = RankConfig(
        topics=["x"],
        keyword_boosts={"y": 0.0},
        source_weights={"s": 1.0},
        search_fields=["title"],
        recency_half_life_hours=24.0,
    )

    a = NewsItem(
        source="s",
        url="https://a.com/1",
        published_at=now - timedelta(hours=1),
        title="x",
        evidence="",
    )
    b = NewsItem(
        source="s",
        url="https://a.com/2",
        published_at=now - timedelta(hours=1),
        title="x",
        evidence="",
    )

    ranked = rank_items([a, b], now=now, top_n=2, cfg=cfg)
    assert ranked[0].url == a.url
    assert ranked[1].url == b.url


def test_top_n_truncates():
    now = datetime(2026, 1, 13, 12, 0, 0, tzinfo=timezone.utc)
    cfg = RankConfig(
        topics=[],
        keyword_boosts={"merger": 5.0},
        source_weights={"s": 1.0},
        search_fields=["title"],
        recency_half_life_hours=24.0,
    )

    a = NewsItem(
        source="s",
        url="https://a.com/1",
        published_at=now - timedelta(hours=1),
        title="merger announced",
        evidence="",
    )
    b = NewsItem(
        source="s",
        url="https://a.com/2",
        published_at=now - timedelta(hours=2),
        title="daily wrap",
        evidence="",
    )
    c = NewsItem(
        source="s",
        url="https://a.com/3",
        published_at=now - timedelta(hours=3),
        title="daily wrap",
        evidence="",
    )

    ranked = rank_items([b, c, a], now=now, top_n=2, cfg=cfg)
    assert len(ranked) == 2
    assert ranked[0].url == a.url

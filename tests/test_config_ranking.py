"""Tests for config-ranking integration (Step 0, Milestone 4.5).

Verifies that user_configs overrides properly flow through to ranking.
"""

import pytest
from datetime import datetime, timezone, timedelta

from src.db import get_conn, init_db
from src.repo import upsert_user_config, get_user_config, create_user
from src.views import get_effective_rank_config
from src.scoring import rank_items, score_item
from src.schemas import NewsItem


@pytest.fixture
def db_conn(tmp_path, monkeypatch):
    """Create a temp database for testing."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))
    conn = get_conn()
    init_db(conn)
    yield conn
    conn.close()


@pytest.fixture
def test_user(db_conn):
    """Create a test user."""
    create_user(db_conn, email="test@example.com", password_hash="fakehash")
    return "test@example.com"


class TestGetEffectiveRankConfig:
    """Tests for get_effective_rank_config function."""

    def test_returns_defaults_when_no_user_config(self, db_conn, test_user):
        """Without user_config, should return RankConfig defaults."""
        cfg = get_effective_rank_config(db_conn, user_id=test_user)

        # Should have default values
        assert cfg.recency_half_life_hours == 24.0
        assert cfg.ai_score_alpha == 0.1

    def test_user_config_overrides_defaults(self, db_conn, test_user):
        """User config should override defaults."""
        # Set user config override
        upsert_user_config(db_conn, user_id=test_user, config={
            "recency_half_life_hours": 48.0,
            "ai_score_alpha": 0.15,
        })

        cfg = get_effective_rank_config(db_conn, user_id=test_user)

        # User overrides should apply
        assert cfg.recency_half_life_hours == 48.0
        assert cfg.ai_score_alpha == 0.15

    def test_source_weight_override_in_config(self, db_conn, test_user):
        """User can override source weights via config."""
        # Set source_weights in user config
        upsert_user_config(db_conn, user_id=test_user, config={
            "source_weights": {"techcrunch": 2.0, "theverge": 0.5},
        })

        cfg = get_effective_rank_config(db_conn, user_id=test_user)

        # Source weights should include user overrides
        assert cfg.source_weights.get("techcrunch") == 2.0
        assert cfg.source_weights.get("theverge") == 0.5


class TestUserConfigAffectsRanking:
    """Tests that user_configs overrides actually affect ranking scores."""

    def test_source_weight_changes_ranking_score(self, db_conn, test_user):
        """Direct user_config source_weight override should change ranking score.

        This is the key Step 0 test: proves config changes flow through to ranking.
        """
        now = datetime(2026, 1, 28, 12, 0, 0, tzinfo=timezone.utc)

        # Use sources that won't have default weights
        item_source_a = NewsItem(
            source="custom_source_a",
            url="https://source-a.com/article",
            published_at=now - timedelta(hours=2),
            title="Tech News",
            evidence="Some evidence",
        )
        item_source_b = NewsItem(
            source="custom_source_b",
            url="https://source-b.com/article",
            published_at=now - timedelta(hours=2),
            title="Tech News",
            evidence="Some evidence",
        )

        # Get config WITHOUT user override - custom sources get default weight 1.0
        cfg_default = get_effective_rank_config(db_conn, user_id=test_user)

        # Score with defaults (both custom sources should have weight 1.0)
        score_a_default = score_item(item_source_a, now=now, cfg=cfg_default)
        score_b_default = score_item(item_source_b, now=now, cfg=cfg_default)

        # Scores should be equal with default weights (both 1.0)
        assert abs(score_a_default - score_b_default) < 0.01, \
            "Default scores should be equal for same-age items with no weight overrides"

        # Now set user config to boost source_a, reduce source_b
        upsert_user_config(db_conn, user_id=test_user, config={
            "source_weights": {"custom_source_a": 2.0, "custom_source_b": 0.5},
        })

        # Get config WITH user override
        cfg_override = get_effective_rank_config(db_conn, user_id=test_user)

        # Verify override applied
        assert cfg_override.source_weights.get("custom_source_a") == 2.0
        assert cfg_override.source_weights.get("custom_source_b") == 0.5

        # Score with user config
        score_a_override = score_item(item_source_a, now=now, cfg=cfg_override)
        score_b_override = score_item(item_source_b, now=now, cfg=cfg_override)

        # Source A should now score higher than Source B
        assert score_a_override > score_b_override, \
            "User config boost should make source_a rank higher"

        # The difference should be significant (2.0 vs 0.5 = 4x)
        assert score_a_override > score_b_override * 2, \
            "Score difference should be significant with 2.0 vs 0.5 weights"

    def test_config_override_affects_rank_order(self, db_conn, test_user):
        """User config should change actual rank order in rank_items()."""
        now = datetime(2026, 1, 28, 12, 0, 0, tzinfo=timezone.utc)

        # Use custom sources to avoid default weight interference
        items = [
            NewsItem(
                source="source_low",
                url="https://source-low.com/article",
                published_at=now - timedelta(hours=1),  # newer
                title="Low Priority Article",
                evidence="Evidence",
            ),
            NewsItem(
                source="source_high",
                url="https://source-high.com/article",
                published_at=now - timedelta(hours=2),  # older
                title="High Priority Article",
                evidence="Evidence",
            ),
        ]

        # Without override, newer item should rank first (equal source weights)
        cfg_default = get_effective_rank_config(db_conn, user_id=test_user)
        ranked_default = rank_items(items, now=now, top_n=2, cfg=cfg_default)

        # The newer item should be first with default weights
        assert ranked_default[0].source == "source_low", \
            "Newer item should rank first with default weights"

        # Set strong override: boost source_high significantly
        upsert_user_config(db_conn, user_id=test_user, config={
            "source_weights": {"source_high": 3.0, "source_low": 0.3},
        })

        # With override, older source_high should rank first despite being older
        cfg_override = get_effective_rank_config(db_conn, user_id=test_user)
        ranked_override = rank_items(items, now=now, top_n=2, cfg=cfg_override)

        assert ranked_override[0].source == "source_high", \
            "User config boost should override recency to rank source_high first"

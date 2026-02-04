"""Tests for advisor_tools.py (Milestone 4.5 Step 2)."""

import pytest
from datetime import datetime, timezone, timedelta

from src.db import get_conn, init_db
from src.repo import (
    create_user,
    insert_news_items,
    upsert_item_feedback,
    insert_suggestion,
    insert_outcome,
    upsert_user_profile,
    upsert_user_config,
)
from src.schemas import NewsItem
from pydantic import HttpUrl

from src.advisor_tools import (
    query_user_feedback,
    query_user_config,
    get_user_profile,
    write_suggestion,
    get_suggestion_outcomes,
    MIN_FEEDBACK_ITEMS,
    MIN_DAYS_HISTORY,
    MAX_CURATED_ITEMS,
    UNGROUNDED_EVIDENCE,
    WEIGHT_OUT_OF_BOUNDS,
    DUPLICATE_SUGGESTION,
    INSUFFICIENT_EVIDENCE,
    TARGET_ON_COOLDOWN,
)


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


@pytest.fixture
def another_user(db_conn):
    """Create another test user for isolation tests."""
    create_user(db_conn, email="other@example.com", password_hash="fakehash")
    return "other@example.com"


def _insert_feedback_items(conn, user_id: str, count: int, days_span: int = 14):
    """Helper to insert feedback items spread over days_span days."""
    now = datetime.now(timezone.utc)

    for i in range(count):
        # Spread items across the date range
        days_ago = int((i / count) * days_span)
        item_date = now - timedelta(days=days_ago)

        # Alternate sources
        sources = ["techcrunch", "arstechnica", "theverge", "wired"]
        source = sources[i % len(sources)]

        # Create news item
        item = NewsItem(
            url=HttpUrl(f"https://example.com/article{i}"),
            title=f"Test Article {i} from {source}",
            source=source,
            evidence=f"Evidence for article {i}",
            published_at=item_date,
            collected_at=item_date,
        )
        insert_news_items(conn, [item])

        # Create feedback (60% liked, 40% disliked)
        useful = 1 if i % 5 != 0 else 0  # ~80% liked for variety
        reason_tag = f"tag_{i % 3}" if i % 2 == 0 else None

        upsert_item_feedback(
            conn,
            run_id=f"run_{i}",
            item_url=f"https://example.com/article{i}",
            useful=useful,
            reason_tag=reason_tag,
            created_at=item_date.isoformat(),
            updated_at=item_date.isoformat(),
            user_id=user_id,
        )


class TestQueryUserFeedback:
    """Tests for query_user_feedback function."""

    def test_returns_insufficient_when_no_feedback(self, db_conn, test_user):
        """No feedback returns insufficient_data=True."""
        result = query_user_feedback(db_conn, user_id=test_user)
        assert result["insufficient_data"] is True
        assert result["meta"]["total_feedback_available"] == 0

    def test_returns_insufficient_when_too_few_items(self, db_conn, test_user):
        """Fewer than MIN_FEEDBACK_ITEMS returns insufficient_data=True."""
        _insert_feedback_items(db_conn, test_user, count=5, days_span=14)

        result = query_user_feedback(db_conn, user_id=test_user)
        assert result["insufficient_data"] is True
        assert "at least 10" in result.get("insufficient_reason", "")

    def test_returns_insufficient_when_too_few_days(self, db_conn, test_user):
        """Fewer than MIN_DAYS_HISTORY returns insufficient_data=True."""
        # Insert 15 items but all on same day (0 days span)
        _insert_feedback_items(db_conn, test_user, count=15, days_span=1)

        result = query_user_feedback(db_conn, user_id=test_user)
        assert result["insufficient_data"] is True
        assert "days" in result.get("insufficient_reason", "").lower()

    def test_returns_curated_items_when_sufficient(self, db_conn, test_user):
        """Sufficient feedback returns curated items."""
        _insert_feedback_items(db_conn, test_user, count=20, days_span=14)

        result = query_user_feedback(db_conn, user_id=test_user)
        assert result["insufficient_data"] is False
        assert len(result["curated_items"]) > 0
        assert result["meta"]["total_feedback_available"] == 20

    def test_computes_source_patterns(self, db_conn, test_user):
        """Source patterns include like_rate and confidence."""
        _insert_feedback_items(db_conn, test_user, count=25, days_span=14)

        result = query_user_feedback(db_conn, user_id=test_user)
        assert "source_patterns" in result
        # Should have patterns for the sources we inserted
        assert len(result["source_patterns"]) > 0

        # Check pattern structure
        for source, pattern in result["source_patterns"].items():
            assert "like_rate" in pattern
            assert "sample_size" in pattern
            assert "confidence" in pattern
            assert pattern["confidence"] in ("high", "medium", "low")

    def test_computes_tag_patterns(self, db_conn, test_user):
        """Tag patterns separate values and dislikes."""
        _insert_feedback_items(db_conn, test_user, count=20, days_span=14)

        result = query_user_feedback(db_conn, user_id=test_user)
        assert "tag_patterns" in result
        assert "values" in result["tag_patterns"]
        assert "dislikes" in result["tag_patterns"]

    def test_respects_max_items_limit(self, db_conn, test_user):
        """Curated items don't exceed MAX_CURATED_ITEMS."""
        _insert_feedback_items(db_conn, test_user, count=100, days_span=30)

        result = query_user_feedback(db_conn, user_id=test_user)
        assert len(result["curated_items"]) <= MAX_CURATED_ITEMS

    def test_user_isolation(self, db_conn, test_user, another_user):
        """User A cannot see User B's feedback."""
        # User A has sufficient feedback
        _insert_feedback_items(db_conn, test_user, count=20, days_span=14)

        # User B has no feedback
        result_b = query_user_feedback(db_conn, user_id=another_user)
        assert result_b["insufficient_data"] is True
        assert result_b["meta"]["total_feedback_available"] == 0


class TestQueryUserConfig:
    """Tests for query_user_config function."""

    def test_returns_defaults_when_no_config(self, db_conn, test_user):
        """No user config returns defaults."""
        result = query_user_config(db_conn, user_id=test_user)
        assert result["has_user_overrides"] is False
        assert result["config"]["topics"] == []
        assert result["config"]["source_weights"] == {}

    def test_returns_user_config_when_set(self, db_conn, test_user):
        """User config overrides are returned."""
        upsert_user_config(
            db_conn,
            user_id=test_user,
            config={
                "topics": ["AI", "kubernetes"],
                "source_weights": {"techcrunch": 1.3},
            },
        )

        result = query_user_config(db_conn, user_id=test_user)
        assert result["has_user_overrides"] is True
        assert "AI" in result["config"]["topics"]
        assert result["config"]["source_weights"].get("techcrunch") == 1.3

    def test_includes_active_weights(self, db_conn, test_user):
        """Active weights from learning loop are included."""
        result = query_user_config(db_conn, user_id=test_user)
        assert "active_weights" in result


class TestGetUserProfileTool:
    """Tests for get_user_profile function."""

    def test_returns_empty_profile_for_new_user(self, db_conn, test_user):
        """New user gets empty profile with is_new_user=True."""
        result = get_user_profile(db_conn, user_id=test_user)
        assert result["is_new_user"] is True
        assert result["total_outcomes"] == 0
        assert result["acceptance_stats"] == {}

    def test_returns_existing_profile(self, db_conn, test_user):
        """Existing profile is returned."""
        upsert_user_profile(
            db_conn,
            user_id=test_user,
            acceptance_stats={"boost_source": {"accepted": 3, "rejected": 1}},
            patterns={"open_to_new_topics": True},
            total_outcomes=4,
        )

        result = get_user_profile(db_conn, user_id=test_user)
        assert result["is_new_user"] is False
        assert result["total_outcomes"] == 4
        assert result["acceptance_stats"]["boost_source"]["accepted"] == 3


class TestWriteSuggestion:
    """Tests for write_suggestion validation."""

    def _setup_feedback(self, conn, user_id):
        """Helper to set up feedback items for validation tests."""
        now = datetime.now(timezone.utc)
        for i in range(5):
            item = NewsItem(
                url=HttpUrl(f"https://evidence.com/item{i}"),
                title=f"Evidence Item {i}",
                source="techcrunch",
                evidence="evidence",
                published_at=now,
                collected_at=now,
            )
            insert_news_items(conn, [item])
            upsert_item_feedback(
                conn,
                run_id="run1",
                item_url=f"https://evidence.com/item{i}",
                useful=1,
                created_at=now.isoformat(),
                updated_at=now.isoformat(),
                user_id=user_id,
            )

    def test_rejects_insufficient_evidence(self, db_conn, test_user):
        """Fewer than 3 evidence items rejected."""
        self._setup_feedback(db_conn, test_user)

        result = write_suggestion(
            db_conn,
            user_id=test_user,
            suggestion_type="add_topic",
            field="topics",
            current_value=None,
            suggested_value="kubernetes",
            evidence_items=[{"url": "https://evidence.com/item0"}],  # Only 1
            reason="Test",
        )

        assert result["success"] is False
        assert result["error"] == INSUFFICIENT_EVIDENCE

    def test_rejects_ungrounded_evidence(self, db_conn, test_user):
        """Evidence URLs not in user feedback rejected."""
        self._setup_feedback(db_conn, test_user)

        result = write_suggestion(
            db_conn,
            user_id=test_user,
            suggestion_type="add_topic",
            field="topics",
            current_value=None,
            suggested_value="kubernetes",
            evidence_items=[
                {"url": "https://fake.com/not-real"},
                {"url": "https://fake.com/also-fake"},
                {"url": "https://fake.com/nope"},
            ],
            reason="Test",
        )

        assert result["success"] is False
        assert result["error"] == UNGROUNDED_EVIDENCE

    def test_rejects_weight_out_of_bounds(self, db_conn, test_user):
        """Weight change > 0.3 rejected."""
        self._setup_feedback(db_conn, test_user)

        result = write_suggestion(
            db_conn,
            user_id=test_user,
            suggestion_type="boost_source",
            field="source_weights",
            current_value="1.0",
            suggested_value="1.5",  # Change of 0.5 > 0.3
            evidence_items=[
                {"url": "https://evidence.com/item0"},
                {"url": "https://evidence.com/item1"},
                {"url": "https://evidence.com/item2"},
            ],
            reason="Test",
        )

        assert result["success"] is False
        assert result["error"] == WEIGHT_OUT_OF_BOUNDS

    def test_rejects_duplicate_suggestion(self, db_conn, test_user):
        """Duplicate pending suggestion rejected."""
        self._setup_feedback(db_conn, test_user)

        # First suggestion succeeds
        result1 = write_suggestion(
            db_conn,
            user_id=test_user,
            suggestion_type="add_topic",
            field="topics",
            current_value=None,
            suggested_value="kubernetes",
            evidence_items=[
                {"url": "https://evidence.com/item0"},
                {"url": "https://evidence.com/item1"},
                {"url": "https://evidence.com/item2"},
            ],
            reason="Test",
        )
        assert result1["success"] is True

        # Duplicate rejected
        result2 = write_suggestion(
            db_conn,
            user_id=test_user,
            suggestion_type="add_topic",
            field="topics",
            current_value=None,
            suggested_value="kubernetes",  # Same value
            evidence_items=[
                {"url": "https://evidence.com/item0"},
                {"url": "https://evidence.com/item1"},
                {"url": "https://evidence.com/item2"},
            ],
            reason="Test 2",
        )

        assert result2["success"] is False
        assert result2["error"] == DUPLICATE_SUGGESTION

    def test_accepts_valid_suggestion(self, db_conn, test_user):
        """Valid suggestion is accepted and returns suggestion_id."""
        self._setup_feedback(db_conn, test_user)

        result = write_suggestion(
            db_conn,
            user_id=test_user,
            suggestion_type="boost_source",
            field="source_weights",
            target_key="techcrunch",
            current_value="1.0",
            suggested_value="1.2",  # Change of 0.2 <= 0.3
            evidence_items=[
                {"url": "https://evidence.com/item0"},
                {"url": "https://evidence.com/item1"},
                {"url": "https://evidence.com/item2"},
            ],
            reason="User liked techcrunch articles",
        )

        assert result["success"] is True
        assert "suggestion_id" in result
        assert result["suggestion_id"] > 0

    def test_rejects_target_on_cooldown(self, db_conn, test_user):
        """Target on cooldown (recently suggested) is rejected."""
        self._setup_feedback(db_conn, test_user)

        # First suggestion for techcrunch succeeds
        result1 = write_suggestion(
            db_conn,
            user_id=test_user,
            suggestion_type="boost_source",
            field="source_weights",
            target_key="techcrunch",
            current_value="1.0",
            suggested_value="1.2",
            evidence_items=[
                {"url": "https://evidence.com/item0"},
                {"url": "https://evidence.com/item1"},
                {"url": "https://evidence.com/item2"},
            ],
            reason="Test",
        )
        assert result1["success"] is True

        # Insert outcome to put techcrunch on cooldown
        insert_outcome(
            db_conn,
            suggestion_id=result1["suggestion_id"],
            user_id=test_user,
            suggestion_type="boost_source",
            suggestion_value="techcrunch",  # target stored as value
            outcome="accepted",
        )

        # Second suggestion for techcrunch rejected due to cooldown
        result2 = write_suggestion(
            db_conn,
            user_id=test_user,
            suggestion_type="reduce_source",  # Different type, same target
            field="source_weights",
            target_key="techcrunch",
            current_value="1.2",
            suggested_value="0.9",
            evidence_items=[
                {"url": "https://evidence.com/item0"},
                {"url": "https://evidence.com/item1"},
                {"url": "https://evidence.com/item2"},
            ],
            reason="Test",
        )

        assert result2["success"] is False
        assert result2["error"] == TARGET_ON_COOLDOWN


class TestGetSuggestionOutcomes:
    """Tests for get_suggestion_outcomes 3-layer retrieval."""

    def _setup_outcomes(self, conn, user_id):
        """Helper to set up outcomes for testing."""
        # Create suggestions and outcomes
        s1 = insert_suggestion(
            conn,
            user_id=user_id,
            suggestion_type="boost_source",
            field="source_weights",
            current_value="1.0",
            suggested_value="1.2",
            evidence_items=[{"url": "a"}] * 3,
            reason="r1",
        )
        s2 = insert_suggestion(
            conn,
            user_id=user_id,
            suggestion_type="add_topic",
            field="topics",
            current_value=None,
            suggested_value="kubernetes",
            evidence_items=[{"url": "b"}] * 3,
            reason="r2",
        )

        o1 = insert_outcome(
            conn,
            suggestion_id=s1,
            user_id=user_id,
            suggestion_type="boost_source",
            suggestion_value="1.2",
            outcome="accepted",
            user_reason="Sounds good",
            config_before={"weights": {"techcrunch": 1.0}},
            config_after={"weights": {"techcrunch": 1.2}},
            evidence_summary=[{"url": "a", "title": "A"}],
        )
        o2 = insert_outcome(
            conn,
            suggestion_id=s2,
            user_id=user_id,
            suggestion_type="add_topic",
            suggestion_value="kubernetes",
            outcome="rejected",
            user_reason="Not interested",
        )

        return [o1, o2]

    def test_search_layer_returns_compact_snippets(self, db_conn, test_user):
        """Search layer returns minimal fields."""
        self._setup_outcomes(db_conn, test_user)

        result = get_suggestion_outcomes(
            db_conn, user_id=test_user, layer="search", query={}
        )

        assert result["layer"] == "search"
        assert result["count"] == 2

        # Check compact format
        for outcome in result["outcomes"]:
            assert "outcome_id" in outcome
            assert "suggestion_type" in outcome
            assert "outcome" in outcome
            # Should NOT have full details
            assert "config_before" not in outcome
            assert "evidence_summary" not in outcome

    def test_search_layer_filters_by_type(self, db_conn, test_user):
        """Search layer can filter by suggestion_type."""
        self._setup_outcomes(db_conn, test_user)

        result = get_suggestion_outcomes(
            db_conn,
            user_id=test_user,
            layer="search",
            query={"suggestion_type": "boost_source"},
        )

        assert result["count"] == 1
        assert result["outcomes"][0]["suggestion_type"] == "boost_source"

    def test_timeline_layer_includes_context(self, db_conn, test_user):
        """Timeline layer includes user_reason and config changes."""
        outcome_ids = self._setup_outcomes(db_conn, test_user)

        result = get_suggestion_outcomes(
            db_conn,
            user_id=test_user,
            layer="timeline",
            query={"outcome_ids": outcome_ids},
        )

        assert result["layer"] == "timeline"
        # Check context fields present
        for outcome in result["outcomes"]:
            assert "user_reason" in outcome
            assert "config_before" in outcome
            assert "config_after" in outcome

    def test_detail_layer_includes_evidence(self, db_conn, test_user):
        """Detail layer includes evidence_summary."""
        outcome_ids = self._setup_outcomes(db_conn, test_user)

        result = get_suggestion_outcomes(
            db_conn,
            user_id=test_user,
            layer="detail",
            query={"outcome_ids": [outcome_ids[0]]},
        )

        assert result["layer"] == "detail"
        assert result["count"] == 1
        assert "evidence_summary" in result["outcomes"][0]

    def test_invalid_layer_returns_error(self, db_conn, test_user):
        """Invalid layer returns error."""
        result = get_suggestion_outcomes(
            db_conn, user_id=test_user, layer="invalid", query={}
        )

        assert "error" in result
        assert "valid_layers" in result

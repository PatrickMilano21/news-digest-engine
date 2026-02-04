"""Tests for config suggestions repo functions (Milestone 4.5 Step 1)."""

import pytest

from src.db import get_conn, init_db
from src.repo import (
    create_user,
    insert_suggestion,
    get_pending_suggestions,
    get_suggestion_by_id,
    update_suggestion_status,
    get_suggestions_for_today,
    insert_outcome,
    get_outcomes_by_user,
    get_outcomes_by_type,
    get_user_profile,
    upsert_user_profile,
    get_daily_spend_by_type,
    start_run,
    finish_run_ok,
    update_run_llm_stats,
    is_target_on_cooldown,
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


class TestConfigSuggestions:
    """Tests for config_suggestions CRUD."""

    def test_insert_and_get_suggestion(self, db_conn, test_user):
        """Can insert and retrieve a suggestion."""
        evidence = [
            {"url": "https://example.com/1", "title": "Article 1", "feedback": "liked"},
            {"url": "https://example.com/2", "title": "Article 2", "feedback": "liked"},
            {"url": "https://example.com/3", "title": "Article 3", "feedback": "liked"},
        ]

        suggestion_id = insert_suggestion(
            db_conn,
            user_id=test_user,
            suggestion_type="boost_source",
            field="source_weights",
            target_key="techcrunch",
            current_value="1.0",
            suggested_value="1.3",
            evidence_items=evidence,
            reason="You liked 3 articles from this source",
        )

        assert suggestion_id is not None
        assert suggestion_id > 0

        # Retrieve by ID
        suggestion = get_suggestion_by_id(db_conn, suggestion_id=suggestion_id)
        assert suggestion is not None
        assert suggestion["user_id"] == test_user
        assert suggestion["suggestion_type"] == "boost_source"
        assert suggestion["field"] == "source_weights"
        assert suggestion["target_key"] == "techcrunch"
        assert suggestion["current_value"] == "1.0"
        assert suggestion["suggested_value"] == "1.3"
        assert suggestion["evidence_count"] == 3
        assert suggestion["status"] == "pending"
        assert len(suggestion["evidence_items"]) == 3

    def test_insert_suggestion_without_target_key(self, db_conn, test_user):
        """Can insert suggestion without target_key (for topics)."""
        evidence = [
            {"url": "https://example.com/1", "title": "Article 1", "feedback": "liked"},
            {"url": "https://example.com/2", "title": "Article 2", "feedback": "liked"},
            {"url": "https://example.com/3", "title": "Article 3", "feedback": "liked"},
        ]

        suggestion_id = insert_suggestion(
            db_conn,
            user_id=test_user,
            suggestion_type="add_topic",
            field="topics",
            current_value=None,
            suggested_value="kubernetes",
            evidence_items=evidence,
            reason="Topic appears frequently",
        )

        suggestion = get_suggestion_by_id(db_conn, suggestion_id=suggestion_id)
        assert suggestion is not None
        assert suggestion["target_key"] is None
        assert suggestion["suggested_value"] == "kubernetes"

    def test_get_pending_suggestions(self, db_conn, test_user):
        """Can get pending suggestions for a user."""
        # Insert two suggestions
        insert_suggestion(
            db_conn,
            user_id=test_user,
            suggestion_type="add_topic",
            field="topics",
            current_value=None,
            suggested_value="kubernetes",
            evidence_items=[{"url": "a", "title": "a", "feedback": "liked"}] * 3,
            reason="Topic appears frequently",
        )
        insert_suggestion(
            db_conn,
            user_id=test_user,
            suggestion_type="boost_source",
            field="source_weights",
            current_value="1.0",
            suggested_value="1.3",
            evidence_items=[{"url": "b", "title": "b", "feedback": "liked"}] * 3,
            reason="Source liked often",
        )

        pending = get_pending_suggestions(db_conn, user_id=test_user)
        assert len(pending) == 2

    def test_update_suggestion_status(self, db_conn, test_user):
        """Can update suggestion status."""
        suggestion_id = insert_suggestion(
            db_conn,
            user_id=test_user,
            suggestion_type="add_topic",
            field="topics",
            current_value=None,
            suggested_value="kubernetes",
            evidence_items=[{"url": "a", "title": "a", "feedback": "liked"}] * 3,
            reason="Topic appears frequently",
        )

        # Status should be pending
        suggestion = get_suggestion_by_id(db_conn, suggestion_id=suggestion_id)
        assert suggestion["status"] == "pending"
        assert suggestion["resolved_at"] is None

        # Update to accepted
        update_suggestion_status(db_conn, suggestion_id=suggestion_id, status="accepted")

        suggestion = get_suggestion_by_id(db_conn, suggestion_id=suggestion_id)
        assert suggestion["status"] == "accepted"
        assert suggestion["resolved_at"] is not None

    def test_get_pending_with_status_filter(self, db_conn, test_user):
        """Can filter by status."""
        suggestion_id = insert_suggestion(
            db_conn,
            user_id=test_user,
            suggestion_type="add_topic",
            field="topics",
            current_value=None,
            suggested_value="kubernetes",
            evidence_items=[{"url": "a", "title": "a", "feedback": "liked"}] * 3,
            reason="Topic appears frequently",
        )

        # Should appear in pending
        pending = get_pending_suggestions(db_conn, user_id=test_user, status="pending")
        assert len(pending) == 1

        # Accept it
        update_suggestion_status(db_conn, suggestion_id=suggestion_id, status="accepted")

        # Should not appear in pending
        pending = get_pending_suggestions(db_conn, user_id=test_user, status="pending")
        assert len(pending) == 0

        # Should appear in accepted
        accepted = get_pending_suggestions(db_conn, user_id=test_user, status="accepted")
        assert len(accepted) == 1

    def test_get_suggestions_for_today(self, db_conn, test_user):
        """Can get suggestions for idempotency check."""
        insert_suggestion(
            db_conn,
            user_id=test_user,
            suggestion_type="add_topic",
            field="topics",
            current_value=None,
            suggested_value="kubernetes",
            evidence_items=[{"url": "a", "title": "a", "feedback": "liked"}] * 3,
            reason="Topic appears frequently",
        )

        from datetime import date
        today = date.today().isoformat()

        suggestions = get_suggestions_for_today(db_conn, user_id=test_user, day=today)
        assert len(suggestions) == 1

        # Different day should return empty
        suggestions = get_suggestions_for_today(db_conn, user_id=test_user, day="2020-01-01")
        assert len(suggestions) == 0

    def test_user_isolation_suggestions(self, db_conn, test_user, another_user):
        """User A cannot see User B's suggestions."""
        # User A's suggestion
        insert_suggestion(
            db_conn,
            user_id=test_user,
            suggestion_type="add_topic",
            field="topics",
            current_value=None,
            suggested_value="kubernetes",
            evidence_items=[{"url": "a", "title": "a", "feedback": "liked"}] * 3,
            reason="For user A",
        )

        # User B's suggestion
        insert_suggestion(
            db_conn,
            user_id=another_user,
            suggestion_type="boost_source",
            field="source_weights",
            current_value="1.0",
            suggested_value="1.5",
            evidence_items=[{"url": "b", "title": "b", "feedback": "liked"}] * 3,
            reason="For user B",
        )

        # User A should only see their suggestion
        user_a_suggestions = get_pending_suggestions(db_conn, user_id=test_user)
        assert len(user_a_suggestions) == 1
        assert user_a_suggestions[0]["suggestion_type"] == "add_topic"

        # User B should only see their suggestion
        user_b_suggestions = get_pending_suggestions(db_conn, user_id=another_user)
        assert len(user_b_suggestions) == 1
        assert user_b_suggestions[0]["suggestion_type"] == "boost_source"


class TestSuggestionOutcomes:
    """Tests for suggestion_outcomes CRUD."""

    def test_insert_and_get_outcome(self, db_conn, test_user):
        """Can insert and retrieve an outcome."""
        # First create a suggestion
        suggestion_id = insert_suggestion(
            db_conn,
            user_id=test_user,
            suggestion_type="boost_source",
            field="source_weights",
            current_value="1.0",
            suggested_value="1.3",
            evidence_items=[{"url": "a", "title": "a", "feedback": "liked"}] * 3,
            reason="Source liked often",
        )

        # Insert outcome
        outcome_id = insert_outcome(
            db_conn,
            suggestion_id=suggestion_id,
            user_id=test_user,
            suggestion_type="boost_source",
            suggestion_value="1.3",
            outcome="accepted",
            user_reason="Sounds good",
            config_before={"source_weights": {"techcrunch": 1.0}},
            config_after={"source_weights": {"techcrunch": 1.3}},
            evidence_summary=[{"url": "a", "title": "a"}],
        )

        assert outcome_id is not None
        assert outcome_id > 0

        # Retrieve
        outcomes = get_outcomes_by_user(db_conn, user_id=test_user)
        assert len(outcomes) == 1
        assert outcomes[0]["outcome"] == "accepted"
        assert outcomes[0]["user_reason"] == "Sounds good"
        assert outcomes[0]["config_before"]["source_weights"]["techcrunch"] == 1.0
        assert outcomes[0]["config_after"]["source_weights"]["techcrunch"] == 1.3

    def test_get_outcomes_by_type(self, db_conn, test_user):
        """Can filter outcomes by suggestion type."""
        # Create suggestions
        s1 = insert_suggestion(
            db_conn, user_id=test_user, suggestion_type="boost_source",
            field="source_weights", current_value="1.0", suggested_value="1.3",
            evidence_items=[{"url": "a"}] * 3, reason="r1",
        )
        s2 = insert_suggestion(
            db_conn, user_id=test_user, suggestion_type="add_topic",
            field="topics", current_value=None, suggested_value="kubernetes",
            evidence_items=[{"url": "b"}] * 3, reason="r2",
        )

        # Insert outcomes
        insert_outcome(
            db_conn, suggestion_id=s1, user_id=test_user,
            suggestion_type="boost_source", suggestion_value="1.3", outcome="accepted",
        )
        insert_outcome(
            db_conn, suggestion_id=s2, user_id=test_user,
            suggestion_type="add_topic", suggestion_value="kubernetes", outcome="rejected",
        )

        # Filter by type
        boost_outcomes = get_outcomes_by_type(db_conn, user_id=test_user, suggestion_type="boost_source")
        assert len(boost_outcomes) == 1
        assert boost_outcomes[0]["outcome"] == "accepted"

        topic_outcomes = get_outcomes_by_type(db_conn, user_id=test_user, suggestion_type="add_topic")
        assert len(topic_outcomes) == 1
        assert topic_outcomes[0]["outcome"] == "rejected"

    def test_user_isolation_outcomes(self, db_conn, test_user, another_user):
        """User A cannot see User B's outcomes."""
        # Create suggestions for each user
        s1 = insert_suggestion(
            db_conn, user_id=test_user, suggestion_type="boost_source",
            field="source_weights", current_value="1.0", suggested_value="1.3",
            evidence_items=[{"url": "a"}] * 3, reason="r1",
        )
        s2 = insert_suggestion(
            db_conn, user_id=another_user, suggestion_type="add_topic",
            field="topics", current_value=None, suggested_value="kubernetes",
            evidence_items=[{"url": "b"}] * 3, reason="r2",
        )

        # Insert outcomes
        insert_outcome(
            db_conn, suggestion_id=s1, user_id=test_user,
            suggestion_type="boost_source", suggestion_value="1.3", outcome="accepted",
        )
        insert_outcome(
            db_conn, suggestion_id=s2, user_id=another_user,
            suggestion_type="add_topic", suggestion_value="kubernetes", outcome="rejected",
        )

        # User A only sees their outcome
        user_a_outcomes = get_outcomes_by_user(db_conn, user_id=test_user)
        assert len(user_a_outcomes) == 1
        assert user_a_outcomes[0]["outcome"] == "accepted"

        # User B only sees their outcome
        user_b_outcomes = get_outcomes_by_user(db_conn, user_id=another_user)
        assert len(user_b_outcomes) == 1
        assert user_b_outcomes[0]["outcome"] == "rejected"

    def test_is_target_on_cooldown_recent(self, db_conn, test_user):
        """Target is on cooldown if recently suggested."""
        # Create a suggestion and outcome for techcrunch
        s1 = insert_suggestion(
            db_conn, user_id=test_user, suggestion_type="boost_source",
            field="source_weights", target_key="techcrunch",
            current_value="1.0", suggested_value="1.3",
            evidence_items=[{"url": "a"}] * 3, reason="r1",
        )
        insert_outcome(
            db_conn, suggestion_id=s1, user_id=test_user,
            suggestion_type="boost_source", suggestion_value="techcrunch",
            outcome="accepted",
        )

        # techcrunch is on cooldown
        assert is_target_on_cooldown(db_conn, user_id=test_user, target_value="techcrunch") is True
        # other sources are not
        assert is_target_on_cooldown(db_conn, user_id=test_user, target_value="arstechnica") is False

    def test_is_target_on_cooldown_user_isolation(self, db_conn, test_user, another_user):
        """Cooldown is per-user."""
        # User A has techcrunch on cooldown
        s1 = insert_suggestion(
            db_conn, user_id=test_user, suggestion_type="boost_source",
            field="source_weights", target_key="techcrunch",
            current_value="1.0", suggested_value="1.3",
            evidence_items=[{"url": "a"}] * 3, reason="r1",
        )
        insert_outcome(
            db_conn, suggestion_id=s1, user_id=test_user,
            suggestion_type="boost_source", suggestion_value="techcrunch",
            outcome="accepted",
        )

        # User A: techcrunch on cooldown
        assert is_target_on_cooldown(db_conn, user_id=test_user, target_value="techcrunch") is True
        # User B: techcrunch NOT on cooldown (user isolation)
        assert is_target_on_cooldown(db_conn, user_id=another_user, target_value="techcrunch") is False


class TestUserPreferenceProfiles:
    """Tests for user_preference_profiles CRUD."""

    def test_upsert_and_get_profile(self, db_conn, test_user):
        """Can create and retrieve a profile."""
        upsert_user_profile(
            db_conn,
            user_id=test_user,
            acceptance_stats={
                "boost_source": {"accepted": 5, "rejected": 2, "rate": 0.71},
                "add_topic": {"accepted": 3, "rejected": 1, "rate": 0.75},
            },
            patterns={
                "open_to_new_topics": True,
                "protective_of_sources": False,
            },
            trends={"engagement": "increasing"},
            total_outcomes=11,
            last_outcome_at="2026-02-02T12:00:00Z",
        )

        profile = get_user_profile(db_conn, user_id=test_user)
        assert profile is not None
        assert profile["user_id"] == test_user
        assert profile["acceptance_stats"]["boost_source"]["rate"] == 0.71
        assert profile["patterns"]["open_to_new_topics"] is True
        assert profile["trends"]["engagement"] == "increasing"
        assert profile["total_outcomes"] == 11

    def test_upsert_updates_existing(self, db_conn, test_user):
        """Upsert updates existing profile."""
        # Create initial profile
        upsert_user_profile(
            db_conn,
            user_id=test_user,
            acceptance_stats={"boost_source": {"accepted": 1, "rejected": 0, "rate": 1.0}},
            patterns={"open_to_new_topics": True},
            total_outcomes=1,
        )

        # Update profile
        upsert_user_profile(
            db_conn,
            user_id=test_user,
            acceptance_stats={"boost_source": {"accepted": 5, "rejected": 2, "rate": 0.71}},
            patterns={"open_to_new_topics": True, "protective_of_sources": True},
            total_outcomes=7,
        )

        profile = get_user_profile(db_conn, user_id=test_user)
        assert profile["total_outcomes"] == 7
        assert profile["acceptance_stats"]["boost_source"]["accepted"] == 5
        assert profile["patterns"]["protective_of_sources"] is True

    def test_get_nonexistent_profile_returns_none(self, db_conn, test_user):
        """Getting nonexistent profile returns None."""
        profile = get_user_profile(db_conn, user_id=test_user)
        assert profile is None


class TestGetDailySpendByType:
    """Tests for get_daily_spend_by_type function."""

    def test_returns_zero_when_no_runs(self, db_conn):
        """No runs for day/type should return 0.0."""
        result = get_daily_spend_by_type(db_conn, day="2026-01-28", run_type="advisor")
        assert result == 0.0

    def test_aggregates_cost_for_type(self, db_conn):
        """Should aggregate costs for specific run type."""
        # Create ingest run
        start_run(db_conn, "run1", "2026-01-28T10:00:00+00:00", received=5, run_type="ingest")
        finish_run_ok(db_conn, "run1", "2026-01-28T10:05:00+00:00",
                      after_dedupe=5, inserted=5, duplicates=0)
        update_run_llm_stats(db_conn, "run1", cache_hits=0, cache_misses=5,
                             total_cost_usd=0.50, saved_cost_usd=0.0, total_latency_ms=1000)

        # Create advisor run
        start_run(db_conn, "run2", "2026-01-28T11:00:00+00:00", received=0, run_type="advisor")
        finish_run_ok(db_conn, "run2", "2026-01-28T11:02:00+00:00",
                      after_dedupe=0, inserted=0, duplicates=0)
        update_run_llm_stats(db_conn, "run2", cache_hits=0, cache_misses=1,
                             total_cost_usd=0.15, saved_cost_usd=0.0, total_latency_ms=500)

        # Check ingest spend
        ingest_spend = get_daily_spend_by_type(db_conn, day="2026-01-28", run_type="ingest")
        assert ingest_spend == 0.50

        # Check advisor spend
        advisor_spend = get_daily_spend_by_type(db_conn, day="2026-01-28", run_type="advisor")
        assert advisor_spend == 0.15

    def test_different_days_isolated(self, db_conn):
        """Costs from different days are not mixed."""
        # Run on day 1
        start_run(db_conn, "run1", "2026-01-28T10:00:00+00:00", received=0, run_type="advisor")
        finish_run_ok(db_conn, "run1", "2026-01-28T10:05:00+00:00",
                      after_dedupe=0, inserted=0, duplicates=0)
        update_run_llm_stats(db_conn, "run1", cache_hits=0, cache_misses=1,
                             total_cost_usd=0.20, saved_cost_usd=0.0, total_latency_ms=500)

        # Run on day 2
        start_run(db_conn, "run2", "2026-01-29T10:00:00+00:00", received=0, run_type="advisor")
        finish_run_ok(db_conn, "run2", "2026-01-29T10:05:00+00:00",
                      after_dedupe=0, inserted=0, duplicates=0)
        update_run_llm_stats(db_conn, "run2", cache_hits=0, cache_misses=1,
                             total_cost_usd=0.30, saved_cost_usd=0.0, total_latency_ms=500)

        # Check each day independently
        day1_spend = get_daily_spend_by_type(db_conn, day="2026-01-28", run_type="advisor")
        assert day1_spend == 0.20

        day2_spend = get_daily_spend_by_type(db_conn, day="2026-01-29", run_type="advisor")
        assert day2_spend == 0.30


class TestGetAllItemFeedbackByUser:
    """Tests for get_all_item_feedback_by_user function."""

    def test_returns_empty_list_when_no_feedback(self, db_conn, test_user):
        """No feedback for user returns empty list."""
        from src.repo import get_all_item_feedback_by_user
        result = get_all_item_feedback_by_user(db_conn, user_id=test_user)
        assert result == []

    def test_returns_feedback_with_metadata(self, db_conn, test_user):
        """Returns feedback joined with news_items metadata."""
        from datetime import datetime, timezone
        from pydantic import HttpUrl
        from src.repo import get_all_item_feedback_by_user, upsert_item_feedback, insert_news_items
        from src.schemas import NewsItem

        now = datetime.now(timezone.utc)

        # Insert news item
        item = NewsItem(
            url=HttpUrl("https://example.com/article1"),
            title="Test Article Title",
            source="techcrunch",
            evidence="Test evidence",
            published_at=now,
            collected_at=now,
        )
        insert_news_items(db_conn, [item])

        # Insert feedback
        upsert_item_feedback(
            db_conn,
            run_id="run1",
            item_url="https://example.com/article1",
            useful=1,
            reason_tag="great content",
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
            user_id=test_user,
        )

        result = get_all_item_feedback_by_user(db_conn, user_id=test_user)
        assert len(result) == 1
        assert result[0]["url"] == "https://example.com/article1"
        assert result[0]["title"] == "Test Article Title"
        assert result[0]["source"] == "techcrunch"
        assert result[0]["useful"] == 1
        assert result[0]["reason_tag"] == "great content"
        assert result[0]["feedback_date"] is not None

    def test_user_isolation(self, db_conn, test_user, another_user):
        """User A cannot see User B's feedback."""
        from datetime import datetime, timezone
        from src.repo import get_all_item_feedback_by_user, upsert_item_feedback

        now = datetime.now(timezone.utc).isoformat()

        # User A feedback
        upsert_item_feedback(
            db_conn, run_id="run1", item_url="https://a.com", useful=1,
            created_at=now, updated_at=now, user_id=test_user
        )

        # User B feedback
        upsert_item_feedback(
            db_conn, run_id="run1", item_url="https://b.com", useful=0,
            created_at=now, updated_at=now, user_id=another_user
        )

        # User A only sees their feedback
        user_a_feedback = get_all_item_feedback_by_user(db_conn, user_id=test_user)
        assert len(user_a_feedback) == 1
        assert user_a_feedback[0]["url"] == "https://a.com"

        # User B only sees their feedback
        user_b_feedback = get_all_item_feedback_by_user(db_conn, user_id=another_user)
        assert len(user_b_feedback) == 1
        assert user_b_feedback[0]["url"] == "https://b.com"

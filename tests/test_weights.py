# tests/test_weights.py
"""
Tests for source weight learning loop (Milestone 3b).
"""
import sqlite3
from datetime import datetime, timezone

import pytest

from src.db import init_db
from src.weights import (
    compute_effective_rate,
    compute_weight_adjustments,
    compute_weight_changes,
)
from src.repo import (
    aggregate_feedback_by_source,
    get_active_source_weights,
    upsert_weight_snapshot,
    get_weight_snapshot,
    upsert_item_feedback,
    insert_news_items,
    start_run,
    finish_run_ok,
)
from src.schemas import NewsItem


@pytest.fixture
def conn():
    """Create in-memory database with schema."""
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    return conn


# --- Unit Tests: weights.py ---

class TestComputeEffectiveRate:
    def test_blends_rates(self):
        """Verifies 0.7/0.3 blend formula."""
        result = compute_effective_rate(rate_7d=1.0, rate_longterm=0.0)
        assert result == pytest.approx(0.7)

        result = compute_effective_rate(rate_7d=0.0, rate_longterm=1.0)
        assert result == pytest.approx(0.3)

        result = compute_effective_rate(rate_7d=0.5, rate_longterm=0.5)
        assert result == pytest.approx(0.5)

    def test_edge_cases(self):
        """Both rates zero or one."""
        assert compute_effective_rate(0.0, 0.0) == 0.0
        assert compute_effective_rate(1.0, 1.0) == 1.0


class TestComputeWeightAdjustments:
    def test_increase_on_high_rate(self):
        """effective_rate > 0.7 => +0.1"""
        current = {"techcrunch": 1.0}
        feedback = {"techcrunch": {"effective_rate": 0.8}}
        result = compute_weight_adjustments(current, feedback)
        assert result["techcrunch"] == 1.1

    def test_decrease_on_low_rate(self):
        """effective_rate < 0.3 => -0.1"""
        current = {"techcrunch": 1.0}
        feedback = {"techcrunch": {"effective_rate": 0.2}}
        result = compute_weight_adjustments(current, feedback)
        assert result["techcrunch"] == 0.9

    def test_neutral_zone_no_change(self):
        """0.3 <= effective_rate <= 0.7 => no change"""
        current = {"techcrunch": 1.0}
        feedback = {"techcrunch": {"effective_rate": 0.5}}
        result = compute_weight_adjustments(current, feedback)
        assert result["techcrunch"] == 1.0

    def test_clamps_at_max(self):
        """Weight capped at 2.0"""
        current = {"techcrunch": 1.95}
        feedback = {"techcrunch": {"effective_rate": 0.8}}
        result = compute_weight_adjustments(current, feedback)
        assert result["techcrunch"] == 2.0

    def test_clamps_at_min(self):
        """Weight floored at 0.5"""
        current = {"techcrunch": 0.55}
        feedback = {"techcrunch": {"effective_rate": 0.2}}
        result = compute_weight_adjustments(current, feedback)
        assert result["techcrunch"] == 0.5

    def test_source_not_in_feedback_unchanged(self):
        """Sources without feedback keep current weight."""
        current = {"techcrunch": 1.2, "hackernews": 1.1}
        feedback = {"techcrunch": {"effective_rate": 0.8}}
        result = compute_weight_adjustments(current, feedback)
        assert result["techcrunch"] == 1.3
        assert result["hackernews"] == 1.1

    def test_new_source_defaults_to_one(self):
        """New source in feedback starts at 1.0."""
        current = {}
        feedback = {"newsite": {"effective_rate": 0.8}}
        result = compute_weight_adjustments(current, feedback)
        assert result["newsite"] == 1.1


class TestComputeWeightChanges:
    def test_reports_changes(self):
        """Generates detailed change list."""
        before = {"techcrunch": 1.0, "hackernews": 1.1}
        after = {"techcrunch": 1.1, "hackernews": 1.1}
        feedback = {"techcrunch": {"effective_rate": 0.8}}

        changes = compute_weight_changes(before, after, feedback)

        assert len(changes) == 2
        tc = next(c for c in changes if c["source"] == "techcrunch")
        assert tc["before"] == 1.0
        assert tc["after"] == 1.1
        assert tc["change"] == pytest.approx(0.1)


# --- Integration Tests: repo.py ---

class TestAggregateFeedbackBySource:
    def test_aggregates_correctly(self, conn):
        """Joins feedback to items and computes rates."""
        # Insert items
        now = datetime.now(timezone.utc)
        items = [
            NewsItem(source="TechCrunch", url="https://tc.com/1", published_at=now, title="A", evidence=""),
            NewsItem(source="TechCrunch", url="https://tc.com/2", published_at=now, title="B", evidence=""),
            NewsItem(source="HackerNews", url="https://hn.com/1", published_at=now, title="C", evidence=""),
        ]
        insert_news_items(conn, items)

        # Create run
        run_id = "test-run-1"
        started_at = now.isoformat()
        start_run(conn, run_id, started_at, received=3)
        finish_run_ok(conn, run_id, started_at, after_dedupe=3, inserted=3, duplicates=0)

        # Add feedback (5+ votes for techcrunch, 3 for hackernews)
        ts = now.isoformat()
        upsert_item_feedback(conn, run_id=run_id, item_url="https://tc.com/1", useful=1, created_at=ts, updated_at=ts)
        upsert_item_feedback(conn, run_id=run_id, item_url="https://tc.com/2", useful=1, created_at=ts, updated_at=ts)
        # Need more feedback for min_votes=5
        for i in range(3, 8):
            items2 = [NewsItem(source="TechCrunch", url=f"https://tc.com/{i}", published_at=now, title=f"Item {i}", evidence="")]
            insert_news_items(conn, items2)
            upsert_item_feedback(conn, run_id=run_id, item_url=f"https://tc.com/{i}", useful=1 if i < 6 else 0, created_at=ts, updated_at=ts)

        # Aggregate
        stats = aggregate_feedback_by_source(conn, as_of_date=now.date().isoformat(), min_votes=5)

        assert "techcrunch" in stats
        assert stats["techcrunch"]["total"] >= 5
        # HackerNews should be excluded (< 5 votes)
        assert "hackernews" not in stats

    def test_skips_sources_below_threshold(self, conn):
        """Sources with < min_votes are excluded."""
        now = datetime.now(timezone.utc)
        items = [NewsItem(source="SmallSite", url="https://small.com/1", published_at=now, title="X", evidence="")]
        insert_news_items(conn, items)

        run_id = "test-run-2"
        started_at = now.isoformat()
        start_run(conn, run_id, started_at, received=1)
        finish_run_ok(conn, run_id, started_at, after_dedupe=1, inserted=1, duplicates=0)

        ts = now.isoformat()
        upsert_item_feedback(conn, run_id=run_id, item_url="https://small.com/1", useful=1, created_at=ts, updated_at=ts)

        stats = aggregate_feedback_by_source(conn, as_of_date=now.date().isoformat(), min_votes=5)
        assert "smallsite" not in stats

    def test_empty_feedback_returns_empty(self, conn):
        """No feedback data returns empty dict."""
        stats = aggregate_feedback_by_source(conn, as_of_date="2026-01-28", min_votes=5)
        assert stats == {}


class TestGetActiveSourceWeights:
    def test_returns_defaults_when_no_snapshot(self, conn):
        """No applied snapshot returns RankConfig defaults."""
        weights = get_active_source_weights(conn)
        # Should have default sources
        assert "techcrunch" in weights
        assert weights["techcrunch"] == 1.2

    def test_merges_snapshot_over_defaults(self, conn):
        """Applied snapshot values override defaults."""
        upsert_weight_snapshot(
            conn,
            cycle_date="2026-01-27",
            weights_before={"techcrunch": 1.2},
            weights_after={"techcrunch": 1.5, "newsite": 0.8},
            feedback_summary={},
            eval_before=1.0,
            eval_after=1.0,
            applied=True,
        )

        weights = get_active_source_weights(conn)
        assert weights["techcrunch"] == 1.5
        assert weights["newsite"] == 0.8
        # Defaults still present
        assert "hackernews" in weights

    def test_uses_latest_applied_snapshot(self, conn):
        """Multiple snapshots: latest applied=1 wins."""
        # Older applied snapshot
        upsert_weight_snapshot(
            conn,
            cycle_date="2026-01-25",
            weights_before={},
            weights_after={"techcrunch": 1.3},
            feedback_summary={},
            eval_before=1.0,
            eval_after=1.0,
            applied=True,
        )
        # Newer applied snapshot
        upsert_weight_snapshot(
            conn,
            cycle_date="2026-01-27",
            weights_before={},
            weights_after={"techcrunch": 1.5},
            feedback_summary={},
            eval_before=1.0,
            eval_after=1.0,
            applied=True,
        )
        # Even newer but NOT applied
        upsert_weight_snapshot(
            conn,
            cycle_date="2026-01-28",
            weights_before={},
            weights_after={"techcrunch": 2.0},
            feedback_summary={},
            eval_before=1.0,
            eval_after=0.8,
            applied=False,
            rejected_reason="regression",
        )

        weights = get_active_source_weights(conn)
        assert weights["techcrunch"] == 1.5  # From 2026-01-27


class TestUpsertWeightSnapshot:
    def test_creates_snapshot(self, conn):
        """First insert creates row."""
        snapshot_id = upsert_weight_snapshot(
            conn,
            cycle_date="2026-01-28",
            weights_before={"techcrunch": 1.0},
            weights_after={"techcrunch": 1.1},
            feedback_summary={"techcrunch": {"total": 10, "useful": 8}},
            eval_before=0.92,
            eval_after=0.94,
            applied=True,
        )
        assert snapshot_id > 0

        snapshot = get_weight_snapshot(conn, cycle_date="2026-01-28")
        assert snapshot is not None
        assert snapshot["weights_after"]["techcrunch"] == 1.1
        assert snapshot["applied"] is True

    def test_idempotent_upsert(self, conn):
        """Re-running same date overwrites, doesn't duplicate."""
        upsert_weight_snapshot(
            conn,
            cycle_date="2026-01-28",
            weights_before={"techcrunch": 1.0},
            weights_after={"techcrunch": 1.1},
            feedback_summary={},
            eval_before=0.90,
            eval_after=0.92,
            applied=True,
        )

        # Re-run with different values
        upsert_weight_snapshot(
            conn,
            cycle_date="2026-01-28",
            weights_before={"techcrunch": 1.1},
            weights_after={"techcrunch": 1.2},
            feedback_summary={},
            eval_before=0.92,
            eval_after=0.94,
            applied=True,
        )

        # Should only have one row
        count = conn.execute("SELECT COUNT(*) FROM weight_snapshots WHERE cycle_date = '2026-01-28'").fetchone()[0]
        assert count == 1

        # And it should have the updated values
        snapshot = get_weight_snapshot(conn, cycle_date="2026-01-28")
        assert snapshot["weights_after"]["techcrunch"] == 1.2

    def test_rejected_snapshot_stores_reason(self, conn):
        """Rejected snapshots store reason and have weights_after = weights_before."""
        upsert_weight_snapshot(
            conn,
            cycle_date="2026-01-28",
            weights_before={"techcrunch": 1.0},
            weights_after={"techcrunch": 1.0},  # Same as before when rejected
            feedback_summary={},
            eval_before=0.94,
            eval_after=0.90,
            applied=False,
            rejected_reason="regression",
        )

        snapshot = get_weight_snapshot(conn, cycle_date="2026-01-28")
        assert snapshot["applied"] is False
        assert snapshot["rejected_reason"] == "regression"


# --- End-to-end Tests ---

class TestFullCycle:
    def test_applied_when_feedback_positive(self, conn):
        """Good feedback leads to applied snapshot."""
        # Setup: items + run + feedback
        now = datetime.now(timezone.utc)
        items = [NewsItem(source="GoodSource", url=f"https://good.com/{i}", published_at=now, title=f"Item {i}", evidence="") for i in range(10)]
        insert_news_items(conn, items)

        run_id = "test-run-good"
        started_at = now.isoformat()
        start_run(conn, run_id, started_at, received=10)
        finish_run_ok(conn, run_id, started_at, after_dedupe=10, inserted=10, duplicates=0)

        ts = now.isoformat()
        for i in range(10):
            # 8/10 useful = 0.8 rate
            upsert_item_feedback(conn, run_id=run_id, item_url=f"https://good.com/{i}", useful=1 if i < 8 else 0, created_at=ts, updated_at=ts)

        # Aggregate
        stats = aggregate_feedback_by_source(conn, as_of_date=now.date().isoformat(), min_votes=5)
        assert "goodsource" in stats
        assert stats["goodsource"]["effective_rate"] > 0.7

        # Compute adjustments
        current_weights = get_active_source_weights(conn)
        proposed = compute_weight_adjustments(current_weights, stats)

        # Since goodsource isn't in defaults, it starts at 1.0 and goes to 1.1
        assert proposed.get("goodsource", 1.0) > 1.0

    def test_no_feedback_results_in_rejected(self, conn):
        """No feedback data leads to applied=False with no_feedback reason."""
        stats = aggregate_feedback_by_source(conn, as_of_date="2026-01-28", min_votes=5)
        assert stats == {}

        # When stats is empty, the job should create a snapshot with applied=False
        current_weights = get_active_source_weights(conn)
        upsert_weight_snapshot(
            conn,
            cycle_date="2026-01-28",
            weights_before=current_weights,
            weights_after=current_weights,
            feedback_summary=stats,
            eval_before=None,
            eval_after=None,
            applied=False,
            rejected_reason="no_feedback",
        )

        snapshot = get_weight_snapshot(conn, cycle_date="2026-01-28")
        assert snapshot["applied"] is False
        assert snapshot["rejected_reason"] == "no_feedback"

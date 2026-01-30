"""Tests for LLM cost cap functionality (Milestone 2)."""

import pytest

from src.db import get_conn, init_db
from src.repo import (
    start_run, finish_run_ok, update_run_llm_stats,
    get_daily_spend, get_daily_refusal_counts, upsert_run_failures,
)
from src.error_codes import COST_BUDGET_EXCEEDED


@pytest.fixture
def db_conn(tmp_path, monkeypatch):
    """Create a temp database for testing."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))
    conn = get_conn()
    init_db(conn)
    yield conn
    conn.close()


class TestGetDailySpend:
    """Tests for get_daily_spend repo function."""

    def test_returns_zero_when_no_runs(self, db_conn):
        """No runs for day should return 0.0."""
        result = get_daily_spend(db_conn, day="2026-01-28")
        assert result == 0.0

    def test_aggregates_cost_from_single_run(self, db_conn):
        """Single run cost should be returned."""
        start_run(db_conn, "run1", "2026-01-28T10:00:00+00:00", received=5)
        finish_run_ok(db_conn, "run1", "2026-01-28T10:05:00+00:00",
                      after_dedupe=5, inserted=5, duplicates=0)
        update_run_llm_stats(db_conn, "run1",
                             cache_hits=0, cache_misses=5,
                             total_cost_usd=0.25, saved_cost_usd=0.0,
                             total_latency_ms=1000)

        result = get_daily_spend(db_conn, day="2026-01-28")
        assert result == 0.25

    def test_aggregates_cost_from_multiple_runs(self, db_conn):
        """Multiple runs on same day should be summed."""
        # Run 1
        start_run(db_conn, "run1", "2026-01-28T10:00:00+00:00", received=5)
        finish_run_ok(db_conn, "run1", "2026-01-28T10:05:00+00:00",
                      after_dedupe=5, inserted=5, duplicates=0)
        update_run_llm_stats(db_conn, "run1",
                             cache_hits=0, cache_misses=5,
                             total_cost_usd=0.25, saved_cost_usd=0.0,
                             total_latency_ms=1000)

        # Run 2
        start_run(db_conn, "run2", "2026-01-28T14:00:00+00:00", received=3)
        finish_run_ok(db_conn, "run2", "2026-01-28T14:05:00+00:00",
                      after_dedupe=3, inserted=3, duplicates=0)
        update_run_llm_stats(db_conn, "run2",
                             cache_hits=0, cache_misses=3,
                             total_cost_usd=0.15, saved_cost_usd=0.0,
                             total_latency_ms=600)

        result = get_daily_spend(db_conn, day="2026-01-28")
        assert result == 0.40

    def test_excludes_different_day(self, db_conn):
        """Runs from different days should not be included."""
        # Run on 2026-01-27
        start_run(db_conn, "run1", "2026-01-27T10:00:00+00:00", received=5)
        finish_run_ok(db_conn, "run1", "2026-01-27T10:05:00+00:00",
                      after_dedupe=5, inserted=5, duplicates=0)
        update_run_llm_stats(db_conn, "run1",
                             cache_hits=0, cache_misses=5,
                             total_cost_usd=0.50, saved_cost_usd=0.0,
                             total_latency_ms=1000)

        # Run on 2026-01-28
        start_run(db_conn, "run2", "2026-01-28T10:00:00+00:00", received=3)
        finish_run_ok(db_conn, "run2", "2026-01-28T10:05:00+00:00",
                      after_dedupe=3, inserted=3, duplicates=0)
        update_run_llm_stats(db_conn, "run2",
                             cache_hits=0, cache_misses=3,
                             total_cost_usd=0.25, saved_cost_usd=0.0,
                             total_latency_ms=600)

        result = get_daily_spend(db_conn, day="2026-01-28")
        assert result == 0.25


class TestGetDailyRefusalCounts:
    """Tests for get_daily_refusal_counts repo function."""

    def test_returns_empty_when_no_failures(self, db_conn):
        """No failures should return empty dict."""
        result = get_daily_refusal_counts(db_conn, day="2026-01-28")
        assert result == {}

    def test_returns_counts_by_code(self, db_conn):
        """Should return counts grouped by error code."""
        start_run(db_conn, "run1", "2026-01-28T10:00:00+00:00", received=5)
        finish_run_ok(db_conn, "run1", "2026-01-28T10:05:00+00:00",
                      after_dedupe=5, inserted=5, duplicates=0)
        upsert_run_failures(db_conn, run_id="run1",
                            breakdown={COST_BUDGET_EXCEEDED: 3, "NO_EVIDENCE": 2})

        result = get_daily_refusal_counts(db_conn, day="2026-01-28")
        assert result[COST_BUDGET_EXCEEDED] == 3
        assert result["NO_EVIDENCE"] == 2


class TestCostCapEnvVar:
    """Tests for LLM_DAILY_CAP_USD environment variable."""

    def test_default_cap_is_one_dollar(self, monkeypatch):
        """Default cap should be $1.00 when env var not set."""
        monkeypatch.delenv("LLM_DAILY_CAP_USD", raising=False)
        # Re-import to pick up env var
        import importlib
        import src.clients.llm_openai as llm_module
        importlib.reload(llm_module)

        assert llm_module.LLM_DAILY_CAP_USD == 1.00

    def test_cap_from_env_var(self, monkeypatch):
        """Cap should be read from env var."""
        monkeypatch.setenv("LLM_DAILY_CAP_USD", "5.00")
        import importlib
        import src.clients.llm_openai as llm_module
        importlib.reload(llm_module)

        assert llm_module.LLM_DAILY_CAP_USD == 5.00


class TestDebugCostsEndpoint:
    """Tests for /debug/costs endpoint."""

    def test_returns_cost_stats(self, tmp_path, monkeypatch):
        """Endpoint should return cost stats."""
        from fastapi.testclient import TestClient
        from src.main import app
        from src.db import get_conn, init_db
        from tests.conftest import create_admin_session

        db_file = tmp_path / "test.db"
        monkeypatch.setenv("NEWS_DB_PATH", str(db_file))
        monkeypatch.setenv("LLM_DAILY_CAP_USD", "2.00")

        conn = get_conn()
        init_db(conn)

        # Add a run with some cost
        start_run(conn, "run1", "2026-01-28T10:00:00+00:00", received=5)
        finish_run_ok(conn, "run1", "2026-01-28T10:05:00+00:00",
                      after_dedupe=5, inserted=5, duplicates=0)
        update_run_llm_stats(conn, "run1",
                             cache_hits=0, cache_misses=5,
                             total_cost_usd=0.75, saved_cost_usd=0.0,
                             total_latency_ms=1000)
        conn.close()

        client = TestClient(app)
        client = create_admin_session(client)
        resp = client.get("/debug/costs?date=2026-01-28")

        assert resp.status_code == 200
        data = resp.json()
        assert data["date"] == "2026-01-28"
        assert data["daily_spend_usd"] == 0.75
        assert data["daily_cap_usd"] == 2.00
        assert data["remaining_usd"] == 1.25
        assert data["budget_exceeded"] is False

    def test_budget_exceeded_flag(self, tmp_path, monkeypatch):
        """budget_exceeded should be True when spend >= cap."""
        from fastapi.testclient import TestClient
        from src.main import app
        from src.db import get_conn, init_db
        from tests.conftest import create_admin_session

        db_file = tmp_path / "test.db"
        monkeypatch.setenv("NEWS_DB_PATH", str(db_file))
        monkeypatch.setenv("LLM_DAILY_CAP_USD", "0.50")

        conn = get_conn()
        init_db(conn)

        # Add a run that exceeds cap
        start_run(conn, "run1", "2026-01-28T10:00:00+00:00", received=5)
        finish_run_ok(conn, "run1", "2026-01-28T10:05:00+00:00",
                      after_dedupe=5, inserted=5, duplicates=0)
        update_run_llm_stats(conn, "run1",
                             cache_hits=0, cache_misses=5,
                             total_cost_usd=0.75, saved_cost_usd=0.0,
                             total_latency_ms=1000)
        conn.close()

        client = TestClient(app)
        client = create_admin_session(client)
        resp = client.get("/debug/costs?date=2026-01-28")

        assert resp.status_code == 200
        data = resp.json()
        assert data["budget_exceeded"] is True
        assert data["remaining_usd"] == 0.0

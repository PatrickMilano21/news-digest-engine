# tests/test_repo.py
import uuid
from datetime import datetime, timezone

from src.db import get_conn, init_db
from src.repo import (
    insert_news_items, start_run, finish_run_ok, finish_run_error,
    get_latest_run, upsert_run_failures,
    get_run_failures_with_sources, insert_run_artifact, get_run_artifacts,
    get_run_by_day, report_top_sources,
    report_failures_by_code, update_run_llm_stats, get_run_by_id,
)
from src.schemas import NewsItem


def test_insert_news_items_is_idempotent(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    conn = get_conn()
    try:
        init_db(conn)

        item = NewsItem(
            source="example",
            url="https://example.com/news?id=1#section",
            published_at="2026-01-10T12:00:00Z",
            title="Hello   world",
            evidence="Some snippet",
        )

        r1 = insert_news_items(conn, [item])
        r2 = insert_news_items(conn, [item])

        assert r1["inserted"] == 1
        assert r1["duplicates"] == 0
        assert r2["inserted"] == 0
        assert r2["duplicates"] == 1

        count = conn.execute("SELECT COUNT(*) FROM news_items;").fetchone()[0]
        assert count == 1
    finally:
        conn.close()


def test_start_run_inserts_row_with_started_status(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    conn = get_conn()
    try:
        init_db(conn)
        run_id = uuid.uuid4().hex
        started_at = datetime.now(timezone.utc).isoformat()

        start_run(conn, run_id, started_at, received=5)

        row = conn.execute(
            "SELECT run_id, status, received FROM runs WHERE run_id = ?;", (run_id,)
        ).fetchone()
        assert row is not None
        assert row[0] == run_id
        assert row[1] == "started"
        assert row[2] == 5
    finally:
        conn.close()


def test_finish_run_ok_updates_counts_and_status(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    conn = get_conn()
    try:
        init_db(conn)
        run_id = uuid.uuid4().hex
        started_at = "2026-01-01T00:00:00+00:00"
        finished_at = "2026-01-01T00:01:00+00:00"

        start_run(conn, run_id, started_at, received=10)
        finish_run_ok(conn, run_id, finished_at, after_dedupe=8, inserted=7, duplicates=3)

        row = conn.execute(
            """
            SELECT status, finished_at, after_dedupe, inserted, duplicates
            FROM runs WHERE run_id = ?;
            """,
            (run_id,),
        ).fetchone()

        assert row == ("ok", finished_at, 8, 7, 3)
    finally:
        conn.close()


def test_finish_run_error_sets_status_and_error_fields(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    conn = get_conn()
    try:
        init_db(conn)
        run_id = uuid.uuid4().hex
        started_at = "2026-01-01T00:00:00+00:00"
        finished_at = "2026-01-01T00:00:10+00:00"

        start_run(conn, run_id, started_at, received=1)
        finish_run_error(conn, run_id, finished_at, error_type="RuntimeError", error_message="boom")

        row = conn.execute(
            """
            SELECT status, finished_at, error_type, error_message
            FROM runs WHERE run_id = ?;
            """,
            (run_id,),
        ).fetchone()

        assert row == ("error", finished_at, "RuntimeError", "boom")
    finally:
        conn.close()


def test_get_latest_run_returns_most_recent_by_started_at(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    conn = get_conn()
    try:
        init_db(conn)

        run_id_old = "old"
        run_id_new = "new"

        start_run(conn, run_id_old, "2026-01-01T00:00:00+00:00", received=1)
        start_run(conn, run_id_new, "2026-01-02T00:00:00+00:00", received=2)

        latest = get_latest_run(conn)
        assert latest is not None
        assert latest["run_id"] == run_id_new
        assert latest["received"] == 2
    finally:
        conn.close()

def test_run_failures_roundtrip(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    conn = get_conn()
    try:
        init_db(conn)
        run_id = "test_run_123"
        breakdown = {"EVAL_MISMATCH_KEYWORD": 2, "EVAL_MISMATCH_RECENCY": 1}
        upsert_run_failures(conn, run_id=run_id, breakdown=breakdown)
        result = get_run_failures_with_sources(conn, run_id=run_id)

        assert result["by_code"] == breakdown
    finally:
        conn.close()


def test_run_artifacts_roundtrip(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    conn = get_conn()
    try:
        init_db(conn)

        run_id = "artifact_test_123"
        insert_run_artifact(conn, run_id=run_id, kind="eval_report", path="artifacts/eval_report_2026-01-18.md")
        insert_run_artifact(conn, run_id=run_id, kind="digest", path="artifacts/digest_2026-01-18.html")

        result = get_run_artifacts(conn, run_id=run_id)

        assert result == {
            "eval_report": "artifacts/eval_report_2026-01-18.md",
            "digest": "artifacts/digest_2026-01-18.html",
        }
    finally:
        conn.close()


def test_start_run_stores_run_type(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    conn = get_conn()
    try:
        init_db(conn)

        start_run(conn, "run_ingest", "2026-01-15T00:00:00+00:00", received=10)
        start_run(conn, "run_eval", "2026-01-15T01:00:00+00:00", received=0, run_type="eval")

        row1 = conn.execute("SELECT run_type FROM runs WHERE run_id = ?", ("run_ingest",)).fetchone()
        row2 = conn.execute("SELECT run_type FROM runs WHERE run_id = ?", ("run_eval",)).fetchone()

        assert row1[0] == "ingest"
        assert row2[0] == "eval"
    finally:
        conn.close()


def test_get_run_by_day_returns_ingest_only(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    conn = get_conn()
    try:
        init_db(conn)

        # Create both types for same day
        start_run(conn, "ingest_run", "2026-01-15T00:00:00+00:00", received=10)
        start_run(conn, "eval_run", "2026-01-15T01:00:00+00:00", received=0, run_type="eval")

        result = get_run_by_day(conn, day="2026-01-15")

        assert result is not None
        assert result["run_id"] == "ingest_run"
        assert result["run_type"] == "ingest"
    finally:
        conn.close()


def test_get_run_by_day_with_run_type_eval(tmp_path, monkeypatch):
    """Test that get_run_by_day can filter by run_type='eval'."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    conn = get_conn()
    try:
        init_db(conn)

        start_run(conn, "ingest_run", "2026-01-15T00:00:00+00:00", received=10)
        start_run(conn, "eval_run", "2026-01-15T01:00:00+00:00", received=0, run_type="eval")

        result = get_run_by_day(conn, day="2026-01-15", run_type="eval")

        assert result is not None
        assert result["run_id"] == "eval_run"
        assert result["run_type"] == "eval"
    finally:
        conn.close()


def test_report_top_sources(tmp_path, monkeypatch):
    # Setup: create DB with test items
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_path))
    conn = get_conn()
    init_db(conn)
    
    # Insert test items with different sources
    # ... (use your existing insert_news_items or direct INSERT)
    
    result = report_top_sources(conn, end_day="2026-01-20", days=7)
    
    assert isinstance(result, list)
    # Add more assertions based on your fixture data


def test_report_failures_by_code_empty(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_path))
    conn = get_conn()
    init_db(conn)

    result = report_failures_by_code(conn, end_day="2026-01-20", days=7)

    assert result == {}


def test_update_run_llm_stats_persists_values(tmp_path, monkeypatch):
    """Test that LLM stats are written and can be read back."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    conn = get_conn()
    try:
        init_db(conn)
        run_id = "llm_stats_test"
        start_run(conn, run_id, "2026-01-20T00:00:00+00:00", received=10)

        update_run_llm_stats(
            conn,
            run_id,
            cache_hits=5,
            cache_misses=3,
            total_cost_usd=0.0025,
            saved_cost_usd=0.0015,
            total_latency_ms=1500,
        )

        # Read back via get_run_by_id
        result = get_run_by_id(conn, run_id=run_id)

        assert result is not None
        assert result["llm_cache_hits"] == 5
        assert result["llm_cache_misses"] == 3
        assert result["llm_total_cost_usd"] == 0.0025
        assert result["llm_saved_cost_usd"] == 0.0015
        assert result["llm_total_latency_ms"] == 1500
    finally:
        conn.close()


def test_update_run_llm_stats_is_idempotent(tmp_path, monkeypatch):
    """Test that calling update_run_llm_stats twice overwrites values."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    conn = get_conn()
    try:
        init_db(conn)
        run_id = "llm_stats_idem"
        start_run(conn, run_id, "2026-01-20T00:00:00+00:00", received=10)

        # First update
        update_run_llm_stats(
            conn, run_id,
            cache_hits=1, cache_misses=1,
            total_cost_usd=0.001, saved_cost_usd=0.0,
            total_latency_ms=100,
        )

        # Second update (should overwrite)
        update_run_llm_stats(
            conn, run_id,
            cache_hits=10, cache_misses=5,
            total_cost_usd=0.005, saved_cost_usd=0.003,
            total_latency_ms=2000,
        )

        result = get_run_by_id(conn, run_id=run_id)
        assert result["llm_cache_hits"] == 10
        assert result["llm_cache_misses"] == 5
        assert result["llm_total_cost_usd"] == 0.005
    finally:
        conn.close()


def test_get_run_by_id_returns_zero_for_null_llm_stats(tmp_path, monkeypatch):
    """Test that runs without LLM stats return 0 defaults."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    conn = get_conn()
    try:
        init_db(conn)
        run_id = "no_llm_stats"
        start_run(conn, run_id, "2026-01-20T00:00:00+00:00", received=10)

        result = get_run_by_id(conn, run_id=run_id)

        assert result is not None
        assert result["llm_cache_hits"] == 0
        assert result["llm_cache_misses"] == 0
        assert result["llm_total_cost_usd"] == 0.0
        assert result["llm_saved_cost_usd"] == 0.0
        assert result["llm_total_latency_ms"] == 0
    finally:
        conn.close()


def test_upsert_run_failures_with_sources(tmp_path, monkeypatch):
    """upsert_run_failures stores failed_sources correctly."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_path))

    conn = get_conn()
    try:
        init_db(conn)

        # Create run first (foreign key)
        run_id = "run-with-sources"
        start_run(conn, run_id, "2026-01-20T00:00:00+00:00", received=5)

        # Upsert failures with sources
        breakdown = {"PARSE_ERROR": 2, "FETCH_ERROR": 1}
        sources = {
            "PARSE_ERROR": ["broken1.xml", "broken2.xml"],
            "FETCH_ERROR": ["https://bad.url/feed"]
        }
        upsert_run_failures(conn, run_id=run_id, breakdown=breakdown, sources=sources)

        # Verify via getter function (not raw SQL)
        result = get_run_failures_with_sources(conn, run_id=run_id)

        assert result["by_code"]["PARSE_ERROR"] == 2
        assert result["by_code"]["FETCH_ERROR"] == 1
        assert result["failed_sources"]["PARSE_ERROR"] == ["broken1.xml", "broken2.xml"]
        assert result["failed_sources"]["FETCH_ERROR"] == ["https://bad.url/feed"]
    finally:
        conn.close()
   
def test_get_run_failures_with_sources_returns_both(tmp_path, monkeypatch):
    """get_run_failures_with_sources returns by_code and failed_sources."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_path))

    conn = get_conn()
    try:
        init_db(conn)

        run_id = "run-get-both"
        start_run(conn, run_id, "2026-01-20T00:00:00+00:00", received=5)

        upsert_run_failures(
            conn,
            run_id=run_id,
            breakdown={"PARSE_ERROR": 1},
            sources={"PARSE_ERROR": ["broken.xml"]}
        )

        # Call the function under test
        result = get_run_failures_with_sources(conn, run_id=run_id)

        # Verify structure
        assert "by_code" in result
        assert "failed_sources" in result
        assert result["by_code"] == {"PARSE_ERROR": 1}
        assert result["failed_sources"] == {"PARSE_ERROR": ["broken.xml"]}
    finally:
        conn.close()


def test_get_run_failures_with_sources_empty_when_no_failures(tmp_path, monkeypatch):
    """Returns empty dicts when no failures recorded."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_path))

    conn = get_conn()
    try:
        init_db(conn)

        run_id = "run-no-failures"
        start_run(conn, run_id, "2026-01-20T00:00:00+00:00", received=5)

        # Don't add any failures - just query
        result = get_run_failures_with_sources(conn, run_id=run_id)

        assert result["by_code"] == {}
        assert result["failed_sources"] == {}
    finally:
        conn.close()


def test_upsert_run_failures_without_sources_backwards_compatible(tmp_path, monkeypatch):
    """Calling without sources parameter still works (backwards compat)."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_path))

    conn = get_conn()
    try:
        init_db(conn)
        
        run_id = "run-no-sources-param"
        start_run(conn, run_id, "2026-01-20T00:00:00+00:00", received=5)

        # Call WITHOUT sources parameter (old style)
        upsert_run_failures(conn, run_id=run_id, breakdown={"SOME_ERROR": 3})
        
        # Should still work and return empty sources
        result = get_run_failures_with_sources(conn, run_id=run_id)
        
        assert result["by_code"] == {"SOME_ERROR": 3}
        assert result["failed_sources"] == {}  # Empty, not error
    finally:
        conn.close()
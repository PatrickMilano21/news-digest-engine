from __future__ import annotations

import sys
import pytest


from datetime import datetime, timezone

from src.db import get_conn, init_db
from src.repo import insert_news_items, get_run_artifacts
from src.schemas import NewsItem
from src.llm_schemas.summary import SummaryResult
from jobs.daily_run import main

import src.clients.llm_openai as llm_module

# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def sample_items():
    """Three items - one will fail summarization."""
    return [
        NewsItem(
            source="test-source",
            url="https://example.com/article-1",
            title="Article One",
            published_at=datetime(2026, 1, 22, 10, 0, 0, tzinfo=timezone.utc),
            evidence="Evidence for article one.",
        ),
        NewsItem(
            source="test-source",
            url="https://example.com/fail-this-one",  # This one will fail
            title="Article Two (Will Fail)",
            published_at=datetime(2026, 1, 22, 11, 0, 0, tzinfo=timezone.utc),
            evidence="Evidence for article two.",
        ),
        NewsItem(
            source="test-source",
            url="https://example.com/article-3",
            title="Article Three",
            published_at=datetime(2026, 1, 22, 12, 0, 0, tzinfo=timezone.utc),
            evidence="Evidence for article three.",
        ),
    ]


@pytest.fixture
def valid_usage():
    """Usage dict for successful summarize calls."""
    return {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "cost_usd": 0.001,
        "latency_ms": 100,
    }


# -----------------------------------------------------------------------------
# Test: Pipeline continues on summarization failure
# -----------------------------------------------------------------------------

def test_pipeline_continues_on_summarization_failure(monkeypatch, sample_items, valid_usage):
    """
    If one item's summarize() throws, the pipeline:
    - Does NOT crash
    - Continues to process other items
    - Completes with return code 0
    """
    # Setup: insert items into DB
    conn = get_conn()
    init_db(conn)
    insert_news_items(conn, sample_items)
    conn.close()

    # Mock summarize to fail on one specific item
    def mock_summarize(item, evidence):
        if "fail-this-one" in item.url:
            raise ConnectionError("Simulated network failure")
        return SummaryResult(
            summary="Test summary",
            tags=["test"],
            citations=[],
            confidence=0.9
        ), valid_usage

    monkeypatch.setattr("jobs.daily_run.summarize", mock_summarize)

    # Run pipeline
    from jobs.daily_run import main

    # Mock sys.argv for argparse
    monkeypatch.setattr("sys.argv", ["daily_run.py", "--date", "2026-01-22"])

    result = main()

    # Verify: run completed (didn't crash)
    assert result == 0, "Pipeline should complete even when one item fails"


def test_digest_written_when_summary_fails(monkeypatch, sample_items, valid_usage):
    """
    Even if a summary fails, the digest artifact should still be written.
    """
    import os

    # Setup: insert items into DB
    conn = get_conn()
    init_db(conn)
    insert_news_items(conn, sample_items)
    conn.close()

    # Mock summarize to fail on one specific item
    def mock_summarize(item, evidence):
        if "fail-this-one" in item.url:
            raise ConnectionError("Simulated network failure")
        return SummaryResult(
            summary="Test summary",
            tags=["test"],
            citations=[],
            confidence=0.9
        ), valid_usage

    monkeypatch.setattr("jobs.daily_run.summarize", mock_summarize)
    monkeypatch.setattr("sys.argv", ["daily_run.py", "--date", "2026-01-22"])

    # Run pipeline
    from jobs.daily_run import main
    main()

    # Verify: digest artifact exists
    digest_path = "artifacts/digest_2026-01-22.html"
    assert os.path.exists(digest_path), "Digest should be written even with failures"


def test_all_summaries_fail_digest_still_written(monkeypatch, sample_items):
    """
    Even if ALL summaries fail, the digest artifact should still exist.
    """
    import os

    # Setup: insert items into DB
    conn = get_conn()
    init_db(conn)
    insert_news_items(conn, sample_items)
    conn.close()

    # Mock summarize to ALWAYS fail
    def mock_summarize_always_fails(item, evidence):
        raise ConnectionError("Everything is broken")

    monkeypatch.setattr("jobs.daily_run.summarize", mock_summarize_always_fails)
    monkeypatch.setattr("sys.argv", ["daily_run.py", "--date", "2026-01-22"])

    # Run pipeline
    from jobs.daily_run import main
    result = main()

    # Verify: run completed
    assert result == 0, "Pipeline should complete even when ALL summaries fail"

    # Verify: digest artifact exists (will show refusals)
    digest_path = "artifacts/digest_2026-01-22.html"
    assert os.path.exists(digest_path), "Digest should be written even with all failures"


def test_pipeline_completes_even_if_digest_fails(monkeypatch, sample_items, valid_usage):
    """
    If digest writing fails (e.g., disk full), pipeline still completes.
    """
    # Setup
    conn = get_conn()
    init_db(conn)
    insert_news_items(conn, sample_items)
    conn.close()

    # Mock summarize to succeed
    def mock_summarize(item, evidence):
        return SummaryResult(
            summary="Test summary",
            tags=["test"],
            citations=[],
            confidence=0.9
        ), valid_usage

    monkeypatch.setattr("jobs.daily_run.summarize", mock_summarize)

    # Mock render_digest_html to throw
    def mock_render_fails(*args, **kwargs):
        raise IOError("Simulated disk full")

    monkeypatch.setattr("jobs.daily_run.render_digest_html", mock_render_fails)
    monkeypatch.setattr("sys.argv", ["daily_run.py", "--date", "2026-01-22"])

    # Run pipeline
    from jobs.daily_run import main
    result = main()

    # Pipeline should still complete (digest failure is logged, not fatal)
    assert result == 0, "Pipeline should complete even when digest writing fails"


def test_daily_run_creates_both_artifacts(tmp_path, monkeypatch):
    """Daily run creates both digest and eval_report artifacts in run_artifacts table."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_path))
    monkeypatch.setattr(sys, "argv", ["daily_run.py", "--date", "2026-01-24", "--mode", "fixtures", "--force"])

    main()

    conn = get_conn()
    try:
        row = conn.execute("SELECT run_id FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
        assert row is not None, "No run was created"
        artifacts = get_run_artifacts(conn, run_id=row[0])
        assert "digest" in artifacts, f"Missing digest artifact. Got: {list(artifacts.keys())}"
        assert "eval_report" in artifacts, f"Missing eval_report artifact. Got: {list(artifacts.keys())}"
    finally:
        conn.close()

def test_daily_run_output_includes_evals_status(tmp_path, monkeypatch, capsys):
    """Daily run output includes evals=PASS or evals=FAIL."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_path))
    monkeypatch.setattr(sys, "argv", ["daily_run.py", "--date", "2026-01-24", "--mode", "fixtures", "--force"])

    main()

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "evals=PASS" in combined or "evals=FAIL" in combined, f"No evals status in output: {combined}"


def test_daily_run_completes_even_if_evals_fail(tmp_path, monkeypatch):
    """Pipeline completes with status=ok even if evals fail (observational)."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_path))
    monkeypatch.setattr(sys, "argv", ["daily_run.py", "--date", "2026-01-24", "--mode", "fixtures", "--force"])

    main()  # Should not raise

    conn = get_conn()
    try:
        row = conn.execute("SELECT status FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
        assert row is not None
        assert row[0] == "ok"
    finally:
        conn.close()


def test_llm_disabled_logs_event(monkeypatch, caplog):
    """When OPENAI_API_KEY not set, logs llm_disabled event."""
    import logging
    import importlib

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    importlib.reload(llm_module)

    item = NewsItem(
        source="test",
        url="https://example.com/article",
        published_at=datetime.now(timezone.utc),
        title="Test Article",
        evidence="Some evidence text here.",
    )

    with caplog.at_level(logging.INFO, logger="news_digest"):
        result, _ = llm_module.summarize(item, item.evidence)

    assert result.refusal == "LLM_DISABLED"

    # log_event uses logging module, so check caplog
    assert "llm_disabled" in caplog.text

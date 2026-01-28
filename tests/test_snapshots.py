"""Snapshot tests for HTML output.

These tests capture expected HTML output and fail if it changes unexpectedly.
This guards against accidental UI regressions.

To update snapshots when changes are intentional:
    UPDATE_SNAPSHOTS=1 pytest tests/test_snapshots.py -v
"""
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.schemas import NewsItem
from src.scoring import RankConfig
from src.artifacts import render_digest_html
from src.llm_schemas.summary import SummaryResult

SNAPSHOTS_DIR = Path(__file__).parent / "snapshots"


def normalize_html(html: str) -> str:
    """Normalize HTML for comparison (remove volatile parts)."""
    # Normalize whitespace
    html = re.sub(r'\s+', ' ', html)
    html = re.sub(r'>\s+<', '><', html)
    return html.strip()


def assert_snapshot(name: str, actual: str):
    """Compare actual output against saved snapshot.

    Args:
        name: Snapshot filename (without extension)
        actual: The actual HTML output to compare

    If UPDATE_SNAPSHOTS=1 is set, saves the actual output as the new snapshot.
    Otherwise, compares against the saved snapshot and fails if different.
    """
    snapshot_path = SNAPSHOTS_DIR / f"{name}.html"

    # Normalize for comparison
    actual_normalized = normalize_html(actual)

    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        # Update mode: save the new snapshot
        snapshot_path.write_text(actual, encoding="utf-8")
        pytest.skip(f"Snapshot updated: {snapshot_path}")
        return

    if not snapshot_path.exists():
        # No snapshot exists - create it
        snapshot_path.write_text(actual, encoding="utf-8")
        pytest.fail(
            f"Snapshot created: {snapshot_path}\n"
            f"Review the snapshot and re-run the test."
        )
        return

    # Compare against saved snapshot
    expected = snapshot_path.read_text(encoding="utf-8")
    expected_normalized = normalize_html(expected)

    if actual_normalized != expected_normalized:
        # Show diff info
        pytest.fail(
            f"Snapshot mismatch: {snapshot_path}\n\n"
            f"If this change is intentional, update the snapshot:\n"
            f"  UPDATE_SNAPSHOTS=1 pytest tests/test_snapshots.py::{name} -v\n\n"
            f"Expected length: {len(expected_normalized)}\n"
            f"Actual length: {len(actual_normalized)}"
        )


# --- Fixtures ---

@pytest.fixture
def sample_items():
    """Sample news items for snapshot tests."""
    return [
        NewsItem(
            source="TechNews",
            url="https://example.com/article-1",
            published_at=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
            title="AI Startup Raises $50M in Series B",
            evidence="The company announced...",
        ),
        NewsItem(
            source="Reuters",
            url="https://example.com/article-2",
            published_at=datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),
            title="Cloud Computing Market Expands",
            evidence="Market research shows...",
        ),
    ]


@pytest.fixture
def sample_run():
    """Sample run record for snapshot tests."""
    return {
        "run_id": "test-run-123",
        "status": "ok",
        "started_at": "2026-01-15T08:00:00+00:00",
        "finished_at": "2026-01-15T08:05:00+00:00",
        "received": 10,
        "after_dedupe": 8,
        "inserted": 8,
        "duplicates": 2,
    }


@pytest.fixture
def sample_summaries():
    """Sample summaries for snapshot tests."""
    return [
        SummaryResult(
            summary="An AI startup has secured $50 million in Series B funding to expand operations.",
            tags=["AI", "Funding", "Startup"],
            citations=[],
            refusal=None,
        ),
        SummaryResult(
            summary=None,
            tags=[],
            citations=[],
            refusal="NO_EVIDENCE",
        ),
    ]


# --- Snapshot Tests ---

def test_snapshot_digest_basic(sample_items, sample_run):
    """Snapshot test for basic digest without summaries."""
    html = render_digest_html(
        day="2026-01-15",
        run=sample_run,
        ranked_items=sample_items,
        explanations=[{}, {}],
        cfg=RankConfig(),
        now=datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc),
        top_n=2,
        summaries=None,
    )

    assert_snapshot("digest_basic", html)


def test_snapshot_digest_with_summaries(sample_items, sample_run, sample_summaries):
    """Snapshot test for digest with summaries and refusals."""
    html = render_digest_html(
        day="2026-01-15",
        run=sample_run,
        ranked_items=sample_items,
        explanations=[{}, {}],
        cfg=RankConfig(),
        now=datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc),
        top_n=2,
        summaries=sample_summaries,
    )

    assert_snapshot("digest_with_summaries", html)


def test_snapshot_digest_empty():
    """Snapshot test for digest with no items."""
    html = render_digest_html(
        day="2026-01-15",
        run=None,
        ranked_items=[],
        explanations=[],
        cfg=RankConfig(),
        now=datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc),
        top_n=10,
        summaries=None,
    )

    assert_snapshot("digest_empty", html)


def test_snapshot_digest_no_run(sample_items):
    """Snapshot test for digest without run record."""
    html = render_digest_html(
        day="2026-01-15",
        run=None,
        ranked_items=sample_items,
        explanations=[{}, {}],
        cfg=RankConfig(),
        now=datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc),
        top_n=2,
        summaries=None,
    )

    assert_snapshot("digest_no_run", html)

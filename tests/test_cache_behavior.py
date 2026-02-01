"""Tests for cache behavior in build_digest.py"""

from __future__ import annotations

import json
import pytest
from datetime import datetime, timezone

from src.db import get_conn, init_db
from src.repo import (
    insert_news_items,
    get_cached_summary,
    insert_cached_summary,
)
from src.schemas import NewsItem
from src.llm_schemas.summary import SummaryResult, Citation
from src.cache_utils import compute_cache_key
from src.clients.llm_openai import MODEL


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def sample_item():
    """A NewsItem with evidence for testing."""
    return NewsItem(
        source="test-source",
        url="https://example.com/article",
        title="Test Article",
        published_at=datetime(2026, 1, 22, 12, 0, 0, tzinfo=timezone.utc),
        evidence="The company announced record profits of $1 billion.",
    )


@pytest.fixture
def valid_summary_result(sample_item):
    """A SummaryResult that passes grounding (citation matches evidence)."""
    return SummaryResult(
        summary="The company had record profits.",
        tags=["business"],
        citations=[
            Citation(
                source_url=str(sample_item.url),
                evidence_snippet="record profits of $1 billion"  # Exact substring of evidence
            )
        ],
        confidence=0.9
    )


@pytest.fixture
def valid_usage():
    """Usage dict returned by summarize()."""
    return {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "cost_usd": 0.001,
        "latency_ms": 500
    }


# -----------------------------------------------------------------------------
# Test: Cache HIT skips LLM call
# -----------------------------------------------------------------------------

def test_cache_hit_skips_llm_call(monkeypatch, sample_item, valid_summary_result, valid_usage):
    """When result is cahced, summarize() should NOT be called."""
    #Setup : insert item into DB and cache
    conn = get_conn()
    init_db(conn)
    insert_news_items(conn, [sample_item])

    cache_key = compute_cache_key(MODEL, sample_item.evidence or "")
    insert_cached_summary(
        conn,
        cache_key=cache_key,
        model_name=MODEL,
        summary_json=json.dumps(valid_summary_result.model_dump()),
        prompt_tokens=valid_usage["prompt_tokens"],
        completion_tokens=valid_usage["completion_tokens"],
        cost_usd=valid_usage["cost_usd"],
        latency_ms=valid_usage["latency_ms"],
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    conn.close()

    #Mock summarize to raise if called
    def should_not_be_called(item,evidence):
        raise AssertionError("summarize() should not be called on cache hit!")
    
    monkeypatch.setattr("jobs.build_digest.summarize", should_not_be_called)

    #Run build_digest
    from jobs.build_digest import main
    result = main(["--date", "2026-01-22"])

    # If we get here without AssertionError, summarize was not called
    assert result == 0


# -----------------------------------------------------------------------------
# Test: Cache MISS calls LLM
# -----------------------------------------------------------------------------

def test_cache_miss_calls_llm(monkeypatch, sample_item, valid_summary_result, valid_usage):
    """When cache is empty, summarize() should be called."""
    
    # Setup: insert item into DB (but NOT into cache)
    conn = get_conn()
    init_db(conn)
    insert_news_items(conn, [sample_item])
    conn.close()
    
    # Track if summarize was called
    call_count = {"value": 0}
    
    def mock_summarize(item, evidence, day=None):
        call_count["value"] += 1
        return valid_summary_result, valid_usage

    monkeypatch.setattr("jobs.build_digest.summarize", mock_summarize)

    # Run build_digest
    from jobs.build_digest import main
    result = main(["--date", "2026-01-22"])
    
    assert result == 0
    assert call_count["value"] >= 1, "summarize() should be called on cache miss"



# -----------------------------------------------------------------------------
# Test: Successful result IS cached
# -----------------------------------------------------------------------------

def test_successful_result_cached(monkeypatch, sample_item, valid_summary_result, valid_usage):
    """After successful summarization + grounding, result should be in cache."""
    
    # Setup: insert item into DB (cache empty)
    conn = get_conn()
    init_db(conn)
    insert_news_items(conn, [sample_item])
    conn.close()
    
    # Mock summarize to return valid result
    def mock_summarize(item, evidence, day=None):
        return valid_summary_result, valid_usage

    monkeypatch.setattr("jobs.build_digest.summarize", mock_summarize)

    # Run build_digest
    from jobs.build_digest import main
    result = main(["--date", "2026-01-22"])
    assert result == 0
    
    # Verify cache was populated
    conn = get_conn()
    cache_key = compute_cache_key(MODEL, sample_item.evidence or "")
    cached = get_cached_summary(conn, cache_key=cache_key)
    conn.close()
    
    assert cached is not None, "Successful result should be cached"
    assert cached["model_name"] == MODEL
    assert cached["prompt_tokens"] == valid_usage["prompt_tokens"]


# -----------------------------------------------------------------------------
# Test: Refusal is NOT cached
# -----------------------------------------------------------------------------

def test_refusal_not_cached(monkeypatch, sample_item, valid_usage):
    """When LLM returns refusal, it should NOT be cached."""
    
    # Setup: insert item into DB
    conn = get_conn()
    init_db(conn)
    insert_news_items(conn, [sample_item])
    conn.close()
    
    # Mock summarize to return refusal
    refusal_result = SummaryResult(refusal="LLM_PARSE_FAIL")

    def mock_summarize(item, evidence, day=None):
        return refusal_result, valid_usage

    monkeypatch.setattr("jobs.build_digest.summarize", mock_summarize)

    # Run build_digest
    from jobs.build_digest import main
    result = main(["--date", "2026-01-22"])
    assert result == 0

    # Verify cache is empty
    conn = get_conn()
    cache_key = compute_cache_key(MODEL, sample_item.evidence or "")
    cached = get_cached_summary(conn, cache_key=cache_key)
    conn.close()
    
    assert cached is None, "Refusal should NOT be cached"


# -----------------------------------------------------------------------------
# Test: Grounding failure is NOT cached
# -----------------------------------------------------------------------------

def test_grounding_fail_not_cached(monkeypatch, sample_item, valid_usage):
    """When grounding fails (citation not in evidence), result should NOT be cached."""
    
    # Setup: insert item into DB
    conn = get_conn()
    init_db(conn)
    insert_news_items(conn, [sample_item])
    conn.close()
    
    # Mock summarize to return result with BAD citation (not in evidence)
    bad_result = SummaryResult(
        summary="The company had record profits.",
        tags=["business"],
        citations=[
            Citation(
                source_url=str(sample_item.url),
                evidence_snippet="this text is NOT in the evidence"  # Grounding will fail
            )
        ],
        confidence=0.9
    )
    
    def mock_summarize(item, evidence, day=None):
        return bad_result, valid_usage

    monkeypatch.setattr("jobs.build_digest.summarize", mock_summarize)

    # Run build_digest
    from jobs.build_digest import main
    result = main(["--date", "2026-01-22"])
    assert result == 0

    # Verify cache is empty (grounding failed, so not cached)
    conn = get_conn()
    cache_key = compute_cache_key(MODEL, sample_item.evidence or "")
    cached = get_cached_summary(conn, cache_key=cache_key)
    conn.close()
    
    assert cached is None, "Grounding failure should NOT be cached"










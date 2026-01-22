"""Tests for summary cache repo functions."""
import json

from src.db import get_conn, init_db
from src.repo import get_cached_summary, insert_cached_summary


# ---------------------------------------------------------------------
# get_cached_summary tests
# ---------------------------------------------------------------------

def test_get_cached_summary_returns_none_when_empty():
    """Cache miss returns None."""
    conn = get_conn()
    try:
        init_db(conn)
        result = get_cached_summary(conn, cache_key="nonexistent_key")

        assert result is None
    finally:
        conn.close()

def test_get_cached_summary_returns_dict_when_found():
    """Cache hit returns dict with all columns."""
    conn = get_conn()
    try:
        init_db(conn)

        # Insert directly for test setup
        conn.execute("""
            INSERT INTO summary_cache
            (cache_key, model_name, summary_json, prompt_tokens,
            completion_tokens, cost_usd, latency_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
            "test_key_abc",
            "gpt-4o-mini",
            '{"summary": "Test summary", "citations": []}',
            150,
            75,
            0.000123,
            850,
            "2026-01-21T14:30:00Z"
        ))
        conn.commit()

        result = get_cached_summary(conn, cache_key="test_key_abc")

        assert result is not None
        assert result["cache_key"] == "test_key_abc"
        assert result["model_name"] == "gpt-4o-mini"
        assert result["summary_json"] == '{"summary": "Test summary", "citations": []}'
        assert result["prompt_tokens"] == 150
        assert result["completion_tokens"] == 75
        assert result["cost_usd"] == 0.000123
        assert result["latency_ms"] == 850
        assert result["created_at"] == "2026-01-21T14:30:00Z"
    finally:
        conn.close()

# ---------------------------------------------------------------------
# insert_cached_summary tests
# ---------------------------------------------------------------------

def test_insert_cached_summary_stores_entry():
    """Insert creates retrievable cache entry."""
    conn = get_conn()
    try:
        init_db(conn)

        insert_cached_summary(
            conn,
            cache_key="new_key_xyz",
            model_name="gpt-4o-mini",
            summary_json='{"summary": "New summary"}',
            prompt_tokens=100,
            completion_tokens=50,
            cost_usd=0.0001,
            latency_ms=500,
            created_at="2026-01-21T15:00:00Z"
        )

        # Verify it's retrievable
        result = get_cached_summary(conn, cache_key="new_key_xyz")

        assert result is not None
        assert result["cache_key"] == "new_key_xyz"
        assert result["summary_json"] == '{"summary": "New summary"}'
    finally:
        conn.close()


def test_insert_cached_summary_is_idempotent():
    """Duplicate insert is ignored (first write wins)."""
    conn = get_conn()
    try:
        init_db(conn)

        # First insert
        insert_cached_summary(
            conn,
            cache_key="idempotent_key",
            model_name="gpt-4o-mini",
            summary_json='{"summary": "First"}',
            prompt_tokens=100,
            completion_tokens=50,
            cost_usd=0.0001,
            latency_ms=500,
            created_at="2026-01-21T15:00:00Z"
        )

        # Second insert with same key but different data
        insert_cached_summary(
            conn,
            cache_key="idempotent_key",
            model_name="gpt-4o-mini",
            summary_json='{"summary": "Second - should be ignored"}',
            prompt_tokens=200,
            completion_tokens=100,
            cost_usd=0.0002,
            latency_ms=1000,
            created_at="2026-01-21T16:00:00Z"
        )

        # Verify first write wins
        result = get_cached_summary(conn, cache_key="idempotent_key")

        assert result["summary_json"] == '{"summary": "First"}'
        assert result["prompt_tokens"] == 100  # Not 200
    finally:
        conn.close()


def test_insert_and_get_roundtrip():
    """Full roundtrip: insert → get returns same data."""
    conn = get_conn()
    try:
        init_db(conn)

        original_data = {
            "cache_key": "roundtrip_key",
            "model_name": "gpt-4o-mini",
            "summary_json": json.dumps({
                "summary": "Apple announced iPhone.",
                "tags": ["tech"],
                "citations": [{"source_url": "http://x.com", "evidence_snippet": "announced iPhone"}]
            }),
            "prompt_tokens": 175,
            "completion_tokens": 80,
            "cost_usd": 0.000145,
            "latency_ms": 920,
            "created_at": "2026-01-21T12:00:00Z"
        }

        insert_cached_summary(conn, **original_data)
        result = get_cached_summary(conn, cache_key="roundtrip_key")

        assert result == original_data
    finally:
        conn.close()

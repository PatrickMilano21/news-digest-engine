"""Tests for summary_cache table creation."""
import pytest

from src.db import get_conn, init_db


def test_summary_cache_table_exists():
    """summary_cache table is created by init_db()."""
    conn = get_conn()
    try:
        init_db(conn)
        #Query table info
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='summary_cache'"
        )
        result = cur.fetchone()
        assert result is not None, "summary_cache table should exist"
        assert result[0] == "summary_cache"
    finally:
        conn.close()

def test_summary_cache_table_columns():
    """summary_cache table has expected columns."""
    conn = get_conn()
    try:
        init_db(conn)
        
        # PRAGMA table_info returns column metadata
        cur = conn.execute("PRAGMA table_info(summary_cache)")
        columns = {row[1]: row[2] for row in cur.fetchall()}  # name: type
        
        assert "cache_key" in columns
        assert "model_name" in columns
        assert "summary_json" in columns
        assert "prompt_tokens" in columns
        assert "completion_tokens" in columns
        assert "cost_usd" in columns
        assert "latency_ms" in columns
        assert "created_at" in columns
    finally:
        conn.close()


def test_summary_cache_primary_key():
    """cache_key is the primary key (enforces uniqueness)."""
    conn = get_conn()
    try:
        init_db(conn)

        # Insert a row
        conn.execute("""
            INSERT INTO summary_cache 
            (cache_key, model_name, summary_json, prompt_tokens, completion_tokens, cost_usd, latency_ms, created_at)   
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ("test_key_123", "gpt-4o-mini", '{"summary": "test"}', 100, 50, 0.001, 500, "2026-01-21T12:00:00Z"))       
        
        # Try to insert duplicate - should fail
        with pytest.raises(Exception):  # IntegrityError
            conn.execute("""
                INSERT INTO summary_cache
                (cache_key, model_name, summary_json, prompt_tokens, completion_tokens, cost_usd, latency_ms, 
created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, ("test_key_123", "gpt-4o-mini", '{"summary": "different"}', 100, 50, 0.001, 500, 
"2026-01-21T12:00:00Z"))
    finally:
        conn.close()
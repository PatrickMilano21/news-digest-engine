"""Tests for cache key computation.

These tests verify that compute_cache_key() produces correct,
deterministic, and collision-resistant cache keys.
"""

from src.cache_utils import compute_cache_key, normalize_evidence, is_cache_expired
from datetime import datetime, timezone, timedelta
# ---------------------------------------------------------------------
# Normalization Tests
# ---------------------------------------------------------------------
def test_normalize_strips_whitespace():
    """Leading/trailing whitespace is removed."""
    assert normalize_evidence("  hello  ") == "hello"


def test_normalize_collapses_internal_spaces():
    """Multiple internal spaces become single space."""
    assert normalize_evidence("hello   world") == "hello world"


def test_normalize_handles_none():
    """None input returns empty string."""
    assert normalize_evidence(None) == ""


def test_normalize_handles_whitespace_only():
    """Whitespace-only input returns empty string."""
    assert normalize_evidence("   \n\t   ") == ""


def test_normalize_handles_newlines_tabs():
    """Newlines and tabs are collapsed to single space."""
    assert normalize_evidence("hello\n\tworld") == "hello world"

# ---------------------------------------------------------------------
# Cache Key: Determinism
# ---------------------------------------------------------------------
def test_same_input_same_key():
    """Identical inputs produce identical keys."""
    key1 = compute_cache_key("gpt-4o-mini", "Apple announced iPhone")
    key2 = compute_cache_key("gpt-4o-mini", "Apple announced iPhone")
    assert key1 == key2

def test_key_is_64_char_hex():
    """Output is 64-character hex string (SHA-256)."""
    key = compute_cache_key("gpt-4o-mini", "test")
    assert len(key) == 64
    assert all(c in "0123456789abcdef" for c in key)


# ---------------------------------------------------------------------
# Cache Key: Different Inputs → Different Keys
# ---------------------------------------------------------------------
def test_different_model_different_key():
    """Different model name produces different key."""
    key1 = compute_cache_key("gpt-4o-mini", "same evidence")
    key2 = compute_cache_key("gpt-4o", "same evidence")
    assert key1 != key2


def test_different_evidence_different_key():
    """Different evidence produces different key."""
    key1 = compute_cache_key("gpt-4o-mini", "Apple announced iPhone")
    key2 = compute_cache_key("gpt-4o-mini", "Google announced Pixel")
    assert key1 != key2


# ---------------------------------------------------------------------
# Cache Key: Whitespace Normalization
# ---------------------------------------------------------------------
def test_whitespace_variations_same_key():
    """Whitespace differences produce same key after normalization."""
    key1 = compute_cache_key("gpt-4o-mini", "Apple announced iPhone")
    key2 = compute_cache_key("gpt-4o-mini", "  Apple announced iPhone  ")
    key3 = compute_cache_key("gpt-4o-mini", "Apple  announced  iPhone")
    key4 = compute_cache_key("gpt-4o-mini", "Apple\n\tannounced\niPhone")

    assert key1 == key2 == key3 == key4


# ---------------------------------------------------------------------
# Cache Key: Edge Cases
# ---------------------------------------------------------------------
def test_empty_evidence():
    """Empty evidence is valid (produces consistent key)."""
    key1 = compute_cache_key("gpt-4o-mini", "")
    key2 = compute_cache_key("gpt-4o-mini", "")
    assert key1 == key2
    assert len(key1) == 64


def test_none_evidence():
    """None evidence treated as empty string."""
    key1 = compute_cache_key("gpt-4o-mini", None)
    key2 = compute_cache_key("gpt-4o-mini", "")
    assert key1 == key2


def test_delimiter_prevents_collision():
    """Delimiter in key format prevents model/evidence collision."""
    # Without delimiter, these could collide:
    # "gpt-4o" + "mini text" vs "gpt-4o-mini" + " text"
    key1 = compute_cache_key("gpt-4o", "mini text")
    key2 = compute_cache_key("gpt-4o-mini", "text")
    assert key1 != key2

# -----------------------------------------------------------------------------
# TTL Tests
# -----------------------------------------------------------------------------

def test_cache_not_expired_when_fresh():
    """Cache entry created 1 hour ago with 24-hour TTL is NOT expired."""
    now = datetime(2026, 1, 22, 12, 0, 0, tzinfo=timezone.utc)
    created_at = now - timedelta(hours=1)
    ttl_seconds = 24 * 60 * 60  # 24 hours

    assert is_cache_expired(created_at, ttl_seconds, now) is False


def test_cache_expired_when_old():
    """Cache entry created 48 hours ago with 24-hour TTL IS expired."""
    now = datetime(2026, 1, 22, 12, 0, 0, tzinfo=timezone.utc)
    created_at = now - timedelta(hours=48)
    ttl_seconds = 24 * 60 * 60  # 24 hours

    assert is_cache_expired(created_at, ttl_seconds, now) is True


def test_cache_expired_at_exact_ttl():
    """Cache entry created exactly 24 hours ago with 24-hour TTL IS expired (boundary)."""
    now = datetime(2026, 1, 22, 12, 0, 0, tzinfo=timezone.utc)
    created_at = now - timedelta(hours=24)
    ttl_seconds = 24 * 60 * 60  # 24 hours

    assert is_cache_expired(created_at, ttl_seconds, now) is True


def test_cache_not_expired_just_before_ttl():
    """Cache entry created 23h59m ago with 24-hour TTL is NOT expired (boundary)."""
    now = datetime(2026, 1, 22, 12, 0, 0, tzinfo=timezone.utc)
    created_at = now - timedelta(hours=23, minutes=59)
    ttl_seconds = 24 * 60 * 60  # 24 hours

    assert is_cache_expired(created_at, ttl_seconds, now) is False
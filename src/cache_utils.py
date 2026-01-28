
"""Cache utilities for LLM summary caching.

Provides deterministic cache key computation for the summary cache.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime


def normalize_evidence(text: str | None) -> str:
    """
    Normalize evidence text for cache key computation.
    
    Rules:
    1. None → empty string
    2. Strip leading/trailing whitespace
    3. Collapse multiple internal spaces to single space
    
    This ensures superficial whitespace differences don't cause cache misses.
    """
    if text is None:
        return ""
    #Strip leading/trailing whitespace
    text = text.strip()
    #Collapse multiple spaces to single space
    text = re.sub(r'\s+', ' ', text)
    return text

def compute_cache_key(model: str, evidence: str | None) -> str:
    """
    Compute deterministic cache key for LLM summary.
    
    Key = SHA256(model|normalized_evidence)
    
    IMPORTANT INVARIANTS:
    - Cache key includes ONLY model and evidence
    - Title, URL, source are NOT included (they are not evidence)
    - This aligns with grounding rule: citations must come from evidence only
    
    Args:
        model: LLM model name (e.g., "gpt-4o-mini")
        evidence: Raw evidence text (will be normalized)
        
    Returns:
        64-character hex string (SHA-256 hash)
    """
    normalized = normalize_evidence(evidence)

    #Delimiter prevents collision between model name and evidence
    raw = f"{model}|{normalized}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def is_cache_expired(created_at: datetime, ttl_seconds: int, now: datetime) -> bool:
    """
    Check if a cache entry has exceeded its TTL.
    Args:
        created_at: when the cache entry was created (timezone-aware)
        ttl_seconds: max age in seconds before expiration
        now: Current time (timezone-aware)
    Returns:
        True if expired (age >= ttl), False if fresh
    """
    age_seconds = (now - created_at).total_seconds()
    return age_seconds >= ttl_seconds
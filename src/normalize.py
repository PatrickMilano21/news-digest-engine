# src/normalize.py
"""
Normalization and deduplication logic.
Pure functions — no side effects, no database access.
"""
from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

if TYPE_CHECKING:
    from src.schemas import NewsItem


# Tracking params to strip during URL canonicalization
TRACKING_PARAMS = frozenset([
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "mc_cid", "mc_eid",
])


def normalize_url(url: str) -> str:
    """
    Canonicalize URL for deduplication:
    - Lowercase scheme + hostname
    - Strip fragment
    - Strip tracking params
    - Sort remaining query params
    """
    parts = urlsplit(url)

    # Lowercase scheme and hostname
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()

    # Parse query params, filter out tracking params, sort
    params = parse_qsl(parts.query)
    filtered = [(k, v) for k, v in params if k.lower() not in TRACKING_PARAMS]
    sorted_params = sorted(filtered)
    query = urlencode(sorted_params)

    # Rebuild URL without fragment
    return urlunsplit((scheme, netloc, parts.path, query, ""))


def normalize_title(title: str) -> str:
    """
    Normalize title for deduplication:
    - Strip leading/trailing whitespace
    - Collapse internal whitespace to single spaces
    """
    stripped = title.strip()
    return re.sub(r"\s+", " ", stripped)


def dedupe_key(url: str, title: str) -> str:
    """
    Stable content key used for idempotency + DB unique constraint.
    SHA256 hash of normalized URL + title.
    """
    nurl = normalize_url(url)
    ntitle = normalize_title(title)
    raw = f"{nurl}|{ntitle}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def normalize_and_dedupe(items: list[NewsItem]) -> list[NewsItem]:
    """
    Remove duplicate items from a list based on dedupe_key.
    Preserves order (first occurrence wins).
    """
    seen: set[str] = set()
    out: list[NewsItem] = []

    for item in items:
        key = dedupe_key(str(item.url), item.title)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)

    return out

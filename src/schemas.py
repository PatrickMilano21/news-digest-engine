from __future__ import annotations

from datetime import datetime
import hashlib
import re
from urllib.parse import urlsplit, urlunsplit


from pydantic import BaseModel, Field, HttpUrl


class NewsItem(BaseModel):
    source: str
    url: HttpUrl
    published_at: datetime
    title: str
    evidence: str

class IngestRequest(BaseModel):
    items: list[NewsItem] = Field(..., min_length=1)


def normalize_url(url: str) -> str:
    """
    Day 1 min normalization
    - string URL fragment (#...)
    """
    parts = urlsplit(url)
    # fragment is parts.fragment; drop it by setting fragment to ""
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def normalize_title(title: str) -> str:
    """
    Day 1 min normalization:
    - strip ends
    - collapse internal whitespace to single spaces
    """
    stripped = title.strip()
    return re.sub(r"\s+", " ", stripped)


def dedupe_key(url: str, title: str) -> str:
    """
    Stable content key used for idempotency + DB unique constraint.
    """
    nurl = normalize_url(url)
    ntitle = normalize_title(title)
    raw = f"{nurl}|{ntitle}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
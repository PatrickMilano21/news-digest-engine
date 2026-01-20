from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class NewsItem(BaseModel):
    source: str
    url: HttpUrl
    published_at: datetime
    title: str
    evidence: str


class IngestRequest(BaseModel):
    items: list[NewsItem] = Field(..., min_length=1)

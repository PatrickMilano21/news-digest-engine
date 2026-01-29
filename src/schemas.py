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


class RunFeedbackRequest(BaseModel):
    """Request body for POST /feedback/run - rate overall digest."""
    run_id: str
    rating: int = Field(..., ge=1, le=5)  # 1-5 stars
    comment: str | None = None


class ItemFeedbackRequest(BaseModel):
    """Request body for POST /feedback/item - rate single item usefulness."""
    run_id: str
    item_url: str
    useful: bool  # True = thumbs up, False = thumbs down
    reason_tag: str | None = None  # Optional user-selected feedback reason (Milestone 3a)
    
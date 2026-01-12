import pytest
from pydantic import ValidationError

from src.schemas import NewsItem

def test_newsitem_valid_payload_parses():
    item = NewsItem(
        source="example",
        url="https://example.com/news?id=123",
        published_at="2026-01-10T12:00:00Z",
        title="Hello world", 
        evidence="Some snippet or reason we kept this item",
    )
    assert item.source == "example"
    assert str(item.url) == "https://example.com/news?id=123"
    assert item.title == "Hello world"

def test_newsitem_bad_url_raises():
    with pytest.raises(ValidationError):
        NewsItem(
            source="example",
            url="not-a-url",
            published_at="2026-01-10T12:00:00Z",
            title="Hello world",
            evidence="Some snippet",
        )
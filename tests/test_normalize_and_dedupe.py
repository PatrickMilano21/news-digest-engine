# tests/test_normalize_and_dedupe.py
from src.normalize import normalize_and_dedupe
from src.schemas import NewsItem


def test_normalize_and_dedupe_removes_duplicates():
    items = [
        NewsItem(
            source="a",
            url="https://example.com/x#1",
            published_at="2026-01-10T12:00:00Z",
            title="Hello   world",
            evidence="e1",
        ),
        NewsItem(
            source="a",
            url="https://example.com/x#2",
            published_at="2026-01-10T12:00:00Z",
            title="Hello world",
            evidence="e2",
        ),
    ]

    out = normalize_and_dedupe(items)
    assert len(out) == 1


def test_normalize_and_dedupe_preserves_order():
    items = [
        NewsItem(
            source="a",
            url="https://example.com/1",
            published_at="2026-01-10T12:00:00Z",
            title="First",
            evidence="e1",
        ),
        NewsItem(
            source="a",
            url="https://example.com/2",
            published_at="2026-01-10T12:00:00Z",
            title="Second",
            evidence="e2",
        ),
    ]

    out = normalize_and_dedupe(items)
    assert [x.title for x in out] == ["First", "Second"]


def test_normalize_and_dedupe_keeps_first_equivalent_item():
    first = NewsItem(
        source="a",
        url="https://example.com/x#frag",
        published_at="2026-01-10T12:00:00Z",
        title=" Hello   world ",
        evidence="first",
    )
    second = NewsItem(
        source="a",
        url="https://example.com/x",
        published_at="2026-01-10T12:00:00Z",
        title="Hello world",
        evidence="second",
    )

    out = normalize_and_dedupe([first, second])
    assert len(out) == 1
    assert out[0].evidence == "first"

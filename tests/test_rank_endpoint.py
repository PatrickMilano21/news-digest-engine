from datetime import datetime, timezone, timedelta

from fastapi.testclient import TestClient

from src.main import app
from src.db import get_conn, init_db
from src.repo import insert_news_items
from src.schemas import NewsItem


def test_rank_endpoint_ranks_by_keyword_relevance():
    client = TestClient(app)

    day = "2026-01-13"
    now = datetime(2026, 1, 13, 12, 0, 0, tzinfo=timezone.utc)

    conn = get_conn()
    try:
        init_db(conn)
        items = [
            NewsItem(
                source="blog",
                url="https://a.com/1",
                published_at=now - timedelta(hours=1),
                title="Daily market wrap",
                evidence="",
            ),
            NewsItem(
                source="blog",
                url="https://a.com/2",
                published_at=now - timedelta(hours=2),
                title="Company announces merger",
                evidence="",
            ),
            NewsItem(
                source="blog",
                url="https://a.com/3",
                published_at=now - timedelta(hours=3),
                title="Another update",
                evidence="nothing",
            ),
        ]
        insert_news_items(conn, items)

    finally:
        conn.close()

    payload = {
        "topics": [],
        "keyword_boosts": {"merger": 5.0},
        "source_weights": {},
        "search_fields": ["title"],
        "recency_half_life_hours": 24.0,
    }

    resp = client.post(f"/rank/{day}", params={"top_n": 2}, json=payload)
    assert resp.status_code == 200

    body = resp.json()
    assert body["count"] == 2
    assert body["items"][0]["url"] == "https://a.com/2"


def test_rank_endpoint_rejects_invalid_date_with_problem_details():
    client = TestClient(app)

    payload = {
        "topics": [],
        "keyword_boosts": {"merger": 5.0},
        "source_weights": {},
        "search_fields": ["title"],
        "recency_half_life_hours": 24.0,
    }

    resp = client.post("/rank/not-a-date", json=payload)
    assert resp.status_code == 400

    body = resp.json()
    assert body["status"] == 400
    assert "code" in body
    assert "message" in body
    assert "request_id" in body
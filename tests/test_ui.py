from __future__ import annotations

from datetime import datetime
import uuid

import pytest
from fastapi.testclient import TestClient

from src.db import get_conn, init_db
from src.repo import start_run, finish_run_ok, insert_news_items
from src.schemas import NewsItem
from src.main import app


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    db_path = tmp_path / "test_news.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_path))
    return TestClient(app)


def seed_items_for_day(day: str) -> list[int]:
    """Seed test items and return their database IDs."""
    items = [
        NewsItem(
            source="test-source",
            url=f"https://example.com/{day}/article-1",
            published_at=datetime.fromisoformat(f"{day}T12:00:00+00:00"),
            title="Test Article One",
            evidence="Evidence for article one",
        ),
        NewsItem(
            source="test-source",
            url=f"https://example.com/{day}/article-2",
            published_at=datetime.fromisoformat(f"{day}T11:00:00+00:00"),
            title="Test Article Two",
            evidence="Evidence for article two",
        ),
    ]

    conn = get_conn()
    try:
        init_db(conn)
        insert_news_items(conn, items)
        rows = conn.execute(
            "SELECT id FROM news_items WHERE substr(published_at, 1, 10) = ? ORDER BY id",
            (day,)
        ).fetchall()
        return [row[0] for row in rows]
    finally:
        conn.close()


# --- /ui/date/{date} tests ---

def test_ui_date_renders_items(client: TestClient):
    day = "2026-01-20"
    item_ids = seed_items_for_day(day)

    resp = client.get(f"/ui/date/{day}")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert f"Items for {day}" in resp.text
    assert "Test Article One" in resp.text
    assert "Test Article Two" in resp.text


def test_ui_date_links_to_items(client: TestClient):
    day = "2026-01-20"
    item_ids = seed_items_for_day(day)

    resp = client.get(f"/ui/date/{day}")

    assert resp.status_code == 200
    for item_id in item_ids:
        assert f"/ui/item/{item_id}" in resp.text


def test_ui_date_404_no_items_returns_html(client: TestClient):
    resp = client.get("/ui/date/2099-01-01")

    assert resp.status_code == 404
    assert "text/html" in resp.headers["content-type"]
    assert "No items found" in resp.text


def test_ui_date_400_invalid_date_returns_html(client: TestClient):
    resp = client.get("/ui/date/not-a-date")

    assert resp.status_code == 400
    assert "text/html" in resp.headers["content-type"]
    assert "Invalid date" in resp.text


# --- /ui/item/{id} tests ---

def test_ui_item_renders_detail(client: TestClient):
    day = "2026-01-20"
    item_ids = seed_items_for_day(day)
    item_id = item_ids[0]

    resp = client.get(f"/ui/item/{item_id}")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Test Article One" in resp.text
    assert "Why Ranked" in resp.text
    assert f"/ui/date/{day}" in resp.text  # back link


def test_ui_item_404_not_found_returns_html(client: TestClient):
    resp = client.get("/ui/item/99999")

    assert resp.status_code == 404
    assert "text/html" in resp.headers["content-type"]
    assert "not found" in resp.text.lower()


def test_ui_item_400_invalid_id_returns_html(client: TestClient):
    resp = client.get("/ui/item/0")

    assert resp.status_code == 400
    assert "text/html" in resp.headers["content-type"]

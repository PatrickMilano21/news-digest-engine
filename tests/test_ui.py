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
    assert f"Digest for {day}" in resp.text
    assert "Test Article One" in resp.text
    assert "Test Article Two" in resp.text


def test_ui_date_links_to_articles(client: TestClient):
    day = "2026-01-20"
    seed_items_for_day(day)

    resp = client.get(f"/ui/date/{day}")

    assert resp.status_code == 200
    # Links go to the actual article URLs now
    assert "https://example.com/" in resp.text


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


# --- / (home page) tests ---

def test_home_page_returns_html(client: TestClient):
    """Home page returns HTML with navigation."""
    resp = client.get("/")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "News Digest Engine" in resp.text


def test_home_page_shows_date_links(client: TestClient):
    """Home page shows links to date pages."""
    day = "2026-01-20"
    seed_items_for_day(day)

    resp = client.get("/")

    assert resp.status_code == 200
    assert f"/ui/date/{day}" in resp.text


def test_home_page_shows_debug_links(client: TestClient):
    """Home page includes links to debug tools."""
    resp = client.get("/")

    assert resp.status_code == 200
    assert "/debug/stats" in resp.text
    assert "/docs" in resp.text
    assert "/health" in resp.text


def test_home_page_shows_recent_runs(client: TestClient):
    """Home page shows recent runs when they exist."""
    # Create a run
    conn = get_conn()
    try:
        init_db(conn)
        run_id = uuid.uuid4().hex
        start_run(conn, run_id=run_id, started_at="2026-01-20T12:00:00Z", received=5)
        finish_run_ok(conn, run_id=run_id, finished_at="2026-01-20T12:01:00Z",
                      after_dedupe=5, inserted=5, duplicates=0)
    finally:
        conn.close()

    resp = client.get("/")

    assert resp.status_code == 200
    assert f"/debug/run/{run_id}" in resp.text

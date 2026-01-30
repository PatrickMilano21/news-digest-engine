from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from src.db import get_conn, init_db
from src.repo import insert_news_items, start_run
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
    seed_items_for_day(day)

    resp = client.get(f"/ui/date/{day}")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert f"News Digest — {day}" in resp.text
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

def test_home_redirects_to_latest_date(client: TestClient):
    """Home page redirects to most recent date's digest (based on runs, not items)."""
    day = "2026-01-20"
    seed_items_for_day(day)

    # Create a run for the day (user_id=None for unauthenticated/global)
    conn = get_conn()
    try:
        init_db(conn)
        started_at = datetime.fromisoformat(f"{day}T12:00:00+00:00")
        start_run(conn, "test-run", started_at, received=10, run_type="ingest", user_id=None)
    finally:
        conn.close()

    # Don't follow redirects to verify redirect behavior
    resp = client.get("/", follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers["location"] == f"/ui/date/{day}"


def test_home_shows_welcome_when_no_data(client: TestClient):
    """Home page shows welcome message when no digests exist."""
    resp = client.get("/")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Welcome to News Digest" in resp.text
    assert "No digests available yet" in resp.text


# --- /api/history tests ---

def test_api_history_returns_dates(client: TestClient):
    """API history endpoint returns dates with ratings."""
    day = "2026-01-20"
    seed_items_for_day(day)

    resp = client.get("/api/history")

    assert resp.status_code == 200
    data = resp.json()
    assert "dates" in data
    assert len(data["dates"]) >= 1
    assert data["dates"][0]["day"] == day


def test_api_history_empty_when_no_data(client: TestClient):
    """API history returns empty list when no digests exist."""
    resp = client.get("/api/history")

    assert resp.status_code == 200
    data = resp.json()
    assert data["dates"] == []


# --- Navigation tests ---

def test_pages_have_hamburger_menu(client: TestClient):
    """All pages include hamburger menu for navigation."""
    day = "2026-01-20"
    seed_items_for_day(day)

    resp = client.get(f"/ui/date/{day}")

    assert resp.status_code == 200
    assert "menu-btn" in resp.text  # hamburger button
    assert "left-nav" in resp.text  # nav panel


# --- /ui/history tests ---

def test_history_page_returns_html(client: TestClient):
    """History page returns HTML."""
    resp = client.get("/ui/history")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "History" in resp.text


def test_history_page_shows_dates(client: TestClient):
    """History page lists available dates."""
    day = "2026-01-20"
    seed_items_for_day(day)

    resp = client.get("/ui/history")

    assert resp.status_code == 200
    assert f"/ui/date/{day}" in resp.text


# --- /ui/config tests ---

def test_config_page_returns_html(client: TestClient):
    """Config page returns HTML with placeholder."""
    resp = client.get("/ui/config")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Config" in resp.text
    assert "Coming Soon" in resp.text

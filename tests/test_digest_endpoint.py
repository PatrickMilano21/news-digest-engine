# tests/test_digest_endpoint.py

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.db import get_conn, init_db
from src.repo import start_run, finish_run_ok, insert_news_items
from src.schemas import NewsItem


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.sqlite"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_path))
    return TestClient(app)


def seed_db(day: str):
    conn = get_conn()
    try:
        init_db(conn)

        run_id = "r1"
        start_run(conn, run_id, f"{day}T00:00:00+00:00", received=2)
        finish_run_ok(
            conn,
            run_id,
            f"{day}T00:01:00+00:00",
            after_dedupe=2,
            inserted=2,
            duplicates=0,
        )

        items = [
            NewsItem(
                source="reuters",
                url="https://example.com/a",
                published_at=datetime(2026, 1, 14, 12, 0, tzinfo=timezone.utc),
                title="AI merger talk",
                evidence="merger rumor",
            ),
            NewsItem(
                source="reuters",
                url="https://example.com/b",
                published_at=datetime(2026, 1, 14, 11, 0, tzinfo=timezone.utc),
                title="Semiconductor update",
                evidence="chips",
            ),
        ]
        insert_news_items(conn, items)
    finally:
        conn.close()


def test_digest_rejects_invalid_date(client):
    resp = client.get("/digest/2026-99-99", params={"top_n": 2})
    assert resp.status_code == 400
    # ProblemDetails JSON
    body = resp.json()
    assert body["status"] == 400


def test_digest_returns_html(client):
    day = "2026-01-14"
    seed_db(day)

    resp = client.get(f"/digest/{day}", params={"top_n": 2})
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert f"Digest for {day}" in resp.text
    assert "Why ranked" in resp.text


def test_digest_404_when_no_data(client):
    day = "2026-01-14"
    resp = client.get(f"/digest/{day}", params={"top_n": 2})
    assert resp.status_code == 404
    body = resp.json()
    assert body["status"] == 404

from __future__ import annotations

from datetime import datetime
import uuid

import pytest
from fastapi.testclient import TestClient

from src.db import get_conn, init_db
from src.repo import start_run, finish_run_ok, upsert_run_failures, insert_run_artifact
from src.main import app


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    db_path = tmp_path / "test_news.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_path))
    return TestClient(app)


def seed_ok_run_for_day(day: str) -> str:
    run_id = uuid.uuid4().hex
    started_at = f"{day}T00:00:00+00:00"
    finished_at = f"{day}T00:01:00+00:00"

    conn = get_conn()
    try:
        init_db(conn)
        start_run(conn, run_id=run_id, started_at=started_at, received=0)
        finish_run_ok(conn, run_id=run_id, finished_at=finished_at, after_dedupe=0, inserted=0, duplicates=0)
    finally:
        conn.close()

    return run_id

def seed_items_for_day(day: str) -> list[int]:
    """Seed test items and return their database IDs."""
    from src.schemas import NewsItem
    from src.repo import insert_news_items
    from datetime import datetime, timezone

    items = [
        NewsItem(
            source="test-source",
            url=f"https://example.com/{day}/article-1",

published_at=datetime.fromisoformat(f"{day}T12:00:00+00:00"),
            title="Test Article One",
            evidence="Some evidence text",
        ),
        NewsItem(
            source="test-source",
            url=f"https://example.com/{day}/article-2",
    
published_at=datetime.fromisoformat(f"{day}T11:00:00+00:00"),
            title="Test Article Two",
            evidence="More evidence",
        ),
    ]
    
    conn = get_conn()
    try:
        init_db(conn)
        insert_news_items(conn, items)
        # Get the IDs that were just inserted
        rows = conn.execute(
            "SELECT id FROM news_items WHERE substr(published_at, 1, 10)   = ? ORDER BY id",
            (day,)
        ).fetchall()
        return [row[0] for row in rows]
    finally:
        conn.close()


def test_ui_date_invalid_date_returns_400(client: TestClient):
    resp = client.get("/ui/date/not-a-date")
    assert resp.status_code == 400


def test_ui_date_valid_links_present(client: TestClient):
    day = "2026-01-14"
    seed_ok_run_for_day(day)
    item_ids = seed_items_for_day(day)

    resp = client.get(f"/ui/date/{day}")
    assert resp.status_code == 200

    html = resp.text
    assert f"Items for {day}" in html
    assert "Test Article One" in html
    assert "Test Article Two" in html
    # Check that item links are present
    for item_id in item_ids:
        assert f"/ui/item/{item_id}" in html


def test_debug_run_not_found_404(client: TestClient):
    resp = client.get("/debug/run/doesnotexist")
    assert resp.status_code == 404


def test_debug_run_returns_artifact_path(client: TestClient):
    day = "2026-01-14"
    run_id = seed_ok_run_for_day(day)

    # Seed artifact
    conn = get_conn()
    try:
        init_db(conn)
        insert_run_artifact(conn, run_id=run_id, kind="digest", path=f"artifacts/digest_{day}.html")
    finally:
        conn.close()

    resp = client.get(f"/debug/run/{run_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == run_id
    assert data["artifact_paths"]["digest"] == f"artifacts/digest_{day}.html"


def test_debug_run_returns_breakdown_and_artifacts(client: TestClient):
    day = "2026-01-14"

    # Seed run
    run_id = uuid.uuid4().hex
    started_at = f"{day}T00:00:00+00:00"
    finished_at = f"{day}T00:01:00+00:00"

    conn = get_conn()
    try:
        init_db(conn)
        start_run(conn, run_id=run_id, started_at=started_at, received=10)
        finish_run_ok(conn, run_id=run_id, finished_at=finished_at,
                      after_dedupe=8, inserted=7, duplicates=1)

        # Seed failure breakdown
        breakdown = {"EVAL_MISMATCH_KEYWORD": 2, "EVAL_MISMATCH_RECENCY": 1}
        upsert_run_failures(conn, run_id=run_id, breakdown=breakdown)

        # Seed artifacts
        insert_run_artifact(conn, run_id=run_id, kind="digest", path=f"artifacts/digest_{day}.html")
        insert_run_artifact(conn, run_id=run_id, kind="eval_report", path=f"artifacts/eval_report_{day}.md")
    finally:
        conn.close()

    # Call endpoint
    resp = client.get(f"/debug/run/{run_id}")
    assert resp.status_code == 200
    data = resp.json()

    # Verify structure
    assert data["run_id"] == run_id
    assert data["failures_by_code"] == breakdown
    assert data["artifact_paths"]["digest"] == f"artifacts/digest_{day}.html"
    assert data["artifact_paths"]["eval_report"] == f"artifacts/eval_report_{day}.md"
    assert "request_id" in data
    assert data["counts"]["received"] == 10
    assert data["counts"]["inserted"] == 7
    assert data["run_type"] == "ingest"

from __future__ import annotations

from datetime import datetime
import uuid

import pytest
from fastapi.testclient import TestClient

from src.db import get_conn, init_db
from src.repo import start_run, finish_run_ok
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

def test_ui_date_invalid_date_returns_400(client: TestClient):
    resp = client.get("/ui/date/not-a-date")
    assert resp.status_code == 400

def test_ui_date_valid_links_present(client: TestClient):
    day = "2026-01-14"
    run_id = seed_ok_run_for_day(day)
    resp = client.get(f"/ui/date/{day}")
    assert resp.status_code == 200
    html = resp.text
    assert f"/artifacts/digest_{day}.html" in html
    assert f"/runs/latest" in html
    assert f"debug/run/{run_id}" in html

def test_debug_run_not_found_404(client: TestClient):
    resp = client.get("/debug/run/doesnotexist")
    assert resp.status_code == 404

def test_debug_run_returns_artifact_path(client: TestClient):
    day = "2026-01-14"
    run_id = seed_ok_run_for_day(day)

    resp = client.get(f"/debug/run/{run_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == run_id
    assert data["artifact_path"] == f"/artifacts/digest_{day}.html"

# tests/test_runs_latest.py
from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def test_runs_latest_404_when_no_runs(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    resp = client.get("/runs/latest")
    assert resp.status_code == 404


def test_runs_latest_returns_latest_after_ingest(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    payload = {
        "items": [
            {
                "source": "example.com",
                "url": "https://example.com/news/1#frag",
                "published_at": "2026-01-10T12:00:00Z",
                "title": "Hello   world",
                "evidence": "Some snippet",
            }
        ]
    }

    r1 = client.post("/ingest/raw", json=payload)
    assert r1.status_code == 200

    r2 = client.get("/runs/latest")
    assert r2.status_code == 200
    data = r2.json()

    assert data["run_id"]
    assert data["status"] == "ok"
    assert data["received"] == 1
    assert data["inserted"] == 1
    assert data["duplicates"] == 0

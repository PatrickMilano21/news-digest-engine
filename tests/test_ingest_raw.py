from fastapi.testclient import TestClient

from src.db import get_conn, init_db
from src.main import app



def test_ingest_raw_happy_path_inserts(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    client = TestClient(app)

    payload = {
        "items": [
            {
                "source": "example",
                "url": "https://example.com/news?id=1",
                "published_at": "2026-01-10T12:00:00Z",
                "title": "Hello world",
                "evidence": "Some snippet",
            }
        ]
    }
    resp = client.post("/ingest/raw", json=payload)
    assert resp.status_code == 200

    body = resp.json()

    assert body["received"] == 1
    assert body["after_dedupe"] == 1
    assert body["inserted"] == 1
    assert body["duplicates"] == 0


    conn = get_conn()
    try: 
        init_db(conn)
        count = conn.execute("SELECT COUNT(*) FROM news_items;").fetchone()[0]
        assert count == 1
    finally:
        conn.close()
    


def test_ingest_raw_missing_url_returns_422(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    client = TestClient(app)

    bad_payload = {
        "items": [
            {
                "source": "example",
                #"url": "https://example.com/news?id=1#section", ##MISSING
                "published_at": "2026-01-10T12:00:00Z",
                "title": "Hello   world",
                "evidence": "Some snippet",
            }
        ]
    }

    resp = client.post("/ingest/raw", json=bad_payload)
    assert resp.status_code == 422   


def test_ingest_raw_duplicate_is_ignored(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    client = TestClient(app)

    payload = {
        "items":[
            {   
                "source": "example",
                "url": "https://example.com/news?id=1#section",
                "published_at": "2026-01-10T12:00:00Z",
                "title": "Hello   world",
                "evidence": "Some snippet",
            }
        ]
    }

    r1 = client.post("/ingest/raw", json=payload)
    r2 = client.post("/ingest/raw", json=payload)

    assert r1.status_code == 200
    assert r2.status_code == 200

    body1 = r1.json()

    assert body1["received"] == 1
    assert body1["after_dedupe"] == 1
    assert body1["inserted"] == 1
    assert body1["duplicates"] == 0

    body2 = r2.json()

    assert body2["received"] == 1
    assert body2["after_dedupe"] == 1
    assert body2["inserted"] == 0
    assert body2["duplicates"] == 1

    conn = get_conn()
    try:
        init_db(conn)
        count = conn.execute("SELECT COUNT(*) FROM news_items;").fetchone()[0]
        assert count == 1
    finally:
        conn.close()



def test_ingest_raw_counts_include_python_dedupes(tmp_path, monkeypatch):

    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    client = TestClient(app)

    payload = {
        "items": [
            {
                "source": "a",
                "url": "https://example.com/x#1",
                "published_at": "2026-01-10T12:00:00Z",
                "title": " Hello   world ",
                "evidence": "e1",
            },
            {
                "source": "a",
                "url": "https://example.com/x#2",
                "published_at": "2026-01-10T12:00:00Z",
                "title": "Hello world",
                "evidence": "e2",
            },
        ]
    }

    r = client.post("/ingest/raw", json=payload)
    assert r.status_code == 200

    body = r.json()

    assert body["received"] == 2
    assert body["after_dedupe"] == 1
    assert body["inserted"] == 1
    assert body["duplicates"] == 1

import sqlite3

from src.db import get_conn, init_db


def test_init_db_creates_news_items_table(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    conn = get_conn()
    try:
        init_db(conn)

        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='news_items';"
        ).fetchone()

        assert row is not None
        assert row[0] == "news_items"
    finally:
        conn.close()


def test_init_db_creates_runs_table(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    conn = get_conn()
    try:
        init_db(conn)

        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='runs';"
        ).fetchone()

        assert row is not None
        assert row[0] == "runs"
    finally:
        conn.close()

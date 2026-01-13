# tests/test_repo.py
import uuid
from datetime import datetime, timezone

from src.db import get_conn, init_db
from src.repo import insert_news_items, start_run, finish_run_ok, finish_run_error, get_latest_run
from src.schemas import NewsItem


def test_insert_news_items_is_idempotent(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    conn = get_conn()
    try:
        init_db(conn)

        item = NewsItem(
            source="example",
            url="https://example.com/news?id=1#section",
            published_at="2026-01-10T12:00:00Z",
            title="Hello   world",
            evidence="Some snippet",
        )

        r1 = insert_news_items(conn, [item])
        r2 = insert_news_items(conn, [item])

        assert r1["inserted"] == 1
        assert r1["duplicates"] == 0
        assert r2["inserted"] == 0
        assert r2["duplicates"] == 1

        count = conn.execute("SELECT COUNT(*) FROM news_items;").fetchone()[0]
        assert count == 1
    finally:
        conn.close()


def test_start_run_inserts_row_with_started_status(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    conn = get_conn()
    try:
        init_db(conn)
        run_id = uuid.uuid4().hex
        started_at = datetime.now(timezone.utc).isoformat()

        start_run(conn, run_id, started_at, received=5)

        row = conn.execute(
            "SELECT run_id, status, received FROM runs WHERE run_id = ?;", (run_id,)
        ).fetchone()
        assert row is not None
        assert row[0] == run_id
        assert row[1] == "started"
        assert row[2] == 5
    finally:
        conn.close()


def test_finish_run_ok_updates_counts_and_status(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    conn = get_conn()
    try:
        init_db(conn)
        run_id = uuid.uuid4().hex
        started_at = "2026-01-01T00:00:00+00:00"
        finished_at = "2026-01-01T00:01:00+00:00"

        start_run(conn, run_id, started_at, received=10)
        finish_run_ok(conn, run_id, finished_at, after_dedupe=8, inserted=7, duplicates=3)

        row = conn.execute(
            """
            SELECT status, finished_at, after_dedupe, inserted, duplicates
            FROM runs WHERE run_id = ?;
            """,
            (run_id,),
        ).fetchone()

        assert row == ("ok", finished_at, 8, 7, 3)
    finally:
        conn.close()


def test_finish_run_error_sets_status_and_error_fields(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    conn = get_conn()
    try:
        init_db(conn)
        run_id = uuid.uuid4().hex
        started_at = "2026-01-01T00:00:00+00:00"
        finished_at = "2026-01-01T00:00:10+00:00"

        start_run(conn, run_id, started_at, received=1)
        finish_run_error(conn, run_id, finished_at, error_type="RuntimeError", error_message="boom")

        row = conn.execute(
            """
            SELECT status, finished_at, error_type, error_message
            FROM runs WHERE run_id = ?;
            """,
            (run_id,),
        ).fetchone()

        assert row == ("error", finished_at, "RuntimeError", "boom")
    finally:
        conn.close()


def test_get_latest_run_returns_most_recent_by_started_at(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    conn = get_conn()
    try:
        init_db(conn)

        run_id_old = "old"
        run_id_new = "new"

        start_run(conn, run_id_old, "2026-01-01T00:00:00+00:00", received=1)
        start_run(conn, run_id_new, "2026-01-02T00:00:00+00:00", received=2)

        latest = get_latest_run(conn)
        assert latest is not None
        assert latest["run_id"] == run_id_new
        assert latest["received"] == 2
    finally:
        conn.close()
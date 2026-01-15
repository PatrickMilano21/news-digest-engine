# tests/test_repo_report.py
from src.db import get_conn, init_db
from src.repo import start_run, finish_run_ok, report_runs_by_day


def test_report_runs_by_day_empty_returns_empty_list(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    conn = get_conn()
    try:
        init_db(conn)
        out = report_runs_by_day(conn, limit=7)
        assert out == []
    finally:
        conn.close()


def test_report_runs_by_day_rolls_up_counts(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    conn = get_conn()
    try:
        init_db(conn)

        # two runs on 2026-01-10
        start_run(conn, "r1", "2026-01-10T10:00:00+00:00", received=5)
        finish_run_ok(conn, "r1", "2026-01-10T10:01:00+00:00", after_dedupe=5, inserted=4, duplicates=1)

        start_run(conn, "r2", "2026-01-10T11:00:00+00:00", received=3)
        finish_run_ok(conn, "r2", "2026-01-10T11:01:00+00:00", after_dedupe=3, inserted=3, duplicates=0)

        # one run on 2026-01-09
        start_run(conn, "r3", "2026-01-09T09:00:00+00:00", received=10)
        finish_run_ok(conn, "r3", "2026-01-09T09:01:00+00:00", after_dedupe=8, inserted=7, duplicates=3)

        out = report_runs_by_day(conn, limit=7)

        assert len(out) == 2
        assert out[0]["day"] == "2026-01-10"
        assert out[0]["runs"] == 2
        assert out[0]["received"] == 8
        assert out[0]["inserted"] == 7
        assert out[0]["duplicates"] == 1

        assert out[1]["day"] == "2026-01-09"
        assert out[1]["runs"] == 1
        assert out[1]["received"] == 10
        assert out[1]["inserted"] == 7
        assert out[1]["duplicates"] == 3
    finally:
        conn.close()

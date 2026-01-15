from __future__ import annotations

import runpy
import sys 
from pathlib import Path 

from src.db import get_conn, init_db


def run_daily(day: str) -> int:
    script = Path("jobs") / "daily_run.py"
    old_argv = sys.argv[:]

    try:
        sys.argv = ["daily_run.py", "--date", day]
        ns = runpy.run_path(str(script), run_name = "__not_main__")
        return int(ns["main"]())
    finally:
        sys.argv = old_argv

def count_ok_runs(day: str) -> int:
    conn = get_conn()
    try:
        init_db(conn)
        row = conn.execute(
            """
            SELECT COUNT(*)
            FROM runs
            WHERE substr(started_at, 1, 10) = ?
              AND status = 'ok';
            """,
            (day,),
        ).fetchone()

        return int(row[0])
    finally:
        conn.close()

def count_all_runs(day: str) -> int:
    conn = get_conn()
    try:
        init_db(conn)
        row = conn.execute(
            """
            SELECT COUNT(*)
            FROM runs
            WHERE substr(started_at, 1, 10) = ?;
            """,
            (day,),
        ).fetchone()

        return int(row[0])
    finally:
        conn.close()

def test_first_run_creates_one_ok_run():
    day = "2026-01-09"
    assert run_daily(day) == 0
    assert count_ok_runs(day) == 1

def test_second_run_same_day_does_not_create_second_ok_run():
    day = "2026-01-09"
    assert run_daily(day) == 0
    assert run_daily(day) == 0
    assert count_ok_runs(day) == 1

def test_second_run_same_day_does_not_create_any_new_run_row():
    day = "2026-01-09"
    assert run_daily(day) == 0
    before = count_all_runs(day)
    assert run_daily(day) == 0
    after = count_all_runs(day)
    assert after == before
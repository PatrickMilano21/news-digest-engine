from __future__ import annotations

import argparse
import uuid
from datetime import date, datetime, timezone
from src.db import get_conn, init_db

from src.logging_utils import log_event
from src.repo import has_successful_run_for_day, start_run, finish_run_ok, get_run_by_day


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    p.add_argument("--mode", default="fixtures", choices = ["fixtures, prod"])

    args = p.parse_args()

    date.fromisoformat(args.date)
    day = args.date

    conn = get_conn()
    try:
        init_db(conn)

        if get_run_by_day(conn, day=day):
            run_id = uuid.uuid4().hex
            log_event("daily_run_skipped", run_id=run_id, day=day, reason="already_ok")
            print(f"SKIP day={day} reason=already_ok")
            return 0
        
        run_id = uuid.uuid4().hex
        log_event("daily_run_started", run_id=run_id, day=day, mode=args.mode)

        run_day = date.fromisoformat(day)
        now_t = datetime.now(timezone.utc).time()

        started_at = datetime.combine(run_day, now_t, tzinfo=timezone.utc).isoformat()
        start_run(conn, run_id=run_id, started_at=started_at, received=0)

        received = 0
        after_dedupe = 0
        inserted = 0
        duplicates = 0

        finished_at = datetime.combine(run_day, datetime.now(timezone.utc).time(), tzinfo=timezone.utc).isoformat()

        finish_run_ok(conn, run_id=run_id, finished_at=finished_at, after_dedupe=after_dedupe, inserted=inserted, duplicates=duplicates)
        log_event("daily_run_finished", run_id=run_id, day=day, status="ok", received=received, after_dedupe=after_dedupe, inserted=inserted, duplicates=duplicates)
        print(f"OK day={day} run_id={run_id}")

        return 0

    finally: 
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

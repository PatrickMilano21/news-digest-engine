# jobs/daily_run.py
from __future__ import annotations

import argparse
import time
import uuid
from datetime import date, datetime, timezone

from src.db import get_conn, init_db
from src.error_codes import PARSE_ERROR
from src.feeds import FEEDS
from src.logging_utils import log_event
from src.repo import (
    start_run,
    finish_run_ok,
    finish_run_error,
    get_run_by_day,
    insert_news_items,
    upsert_run_failures,
    write_audit_log
)
from src.rss_fetch import fetch_rss_with_retry
from src.rss_parse import parse_rss
from src.normalize import normalize_and_dedupe
from src.weekly_report import write_weekly_report


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    p.add_argument("--mode", default="fixtures", choices=["fixtures", "prod"])
    args = p.parse_args()

    # Validate date
    date.fromisoformat(args.date)
    day = args.date

    failures: dict[str, int] = {}
    t0: float = 0.0

    conn = get_conn()
    try:
        init_db(conn)

        # Idempotency: skip if already have successful ingest for this day
        if get_run_by_day(conn, day=day):
            run_id = uuid.uuid4().hex
            log_event("daily_run_skipped", run_id=run_id, day=day, reason="already_ok")
            print(f"SKIP day={day} reason=already_ok")
            return 0

        # Start run
        run_id = uuid.uuid4().hex
        t0 = time.perf_counter()
        log_event("daily_run_started", run_id=run_id, day=day, mode=args.mode)

        run_day = date.fromisoformat(day)
        now_t = datetime.now(timezone.utc).time()
        started_at = datetime.combine(run_day, now_t, tzinfo=timezone.utc).isoformat()
        start_run(conn, run_id=run_id, started_at=started_at, received=0)
        write_audit_log(conn, event_type="RUN_STARTED", ts=started_at, run_id=run_id, day=day, details={})

        # Loop feeds
        all_items = []

        for feed in FEEDS:
            url = feed["url"]
            source = feed["source"]

            result = fetch_rss_with_retry(url)

            if not result.ok:
                # Log and record failure
                log_event(
                    "feed_fetch_failed",
                    run_id=run_id,
                    url=url,
                    error_code=result.error_code,
                    error_message=result.error_message,
                )
                # Count by error code
                code = result.error_code or "UNKNOWN"
                failures[code] = failures.get(code, 0) + 1
                continue

            # Parse RSS
            try:
                items = parse_rss(result.content, source=source)
                all_items.extend(items)
                log_event("feed_fetch_ok", run_id=run_id, url=url, items=len(items))
            except Exception as exc:
                log_event(
                    "feed_parse_failed",
                    run_id=run_id,
                    url=url,
                    error=str(exc),
                )
                failures[PARSE_ERROR] = failures.get(PARSE_ERROR, 0) + 1
                continue

        # Store failures
        if failures:
            upsert_run_failures(conn, run_id=run_id, breakdown=failures)

        # Dedupe and ingest
        received = len(all_items)
        deduped = normalize_and_dedupe(all_items)
        after_dedupe = len(deduped)

        if deduped:
            result = insert_news_items(conn, deduped)
            inserted = result["inserted"]
            duplicates = (received - after_dedupe) + result["duplicates"]
        else:
            inserted = 0
            duplicates = 0

        # Finish run
        finished_at = datetime.combine(
            run_day, datetime.now(timezone.utc).time(), tzinfo=timezone.utc
        ).isoformat()

        # Update received count now that we know it
        conn.execute("UPDATE runs SET received = ? WHERE run_id = ?", (received, run_id))
        conn.commit()

        finish_run_ok(
            conn,
            run_id=run_id,
            finished_at=finished_at,
            after_dedupe=after_dedupe,
            inserted=inserted,
            duplicates=duplicates,
        )
        write_audit_log(conn, event_type="RUN_FINISHED_OK", ts=finished_at, run_id=run_id, day=day, details={"inserted": inserted, "duplicates": duplicates})

        # Generate weekly report (best-effort)
        try:
            write_weekly_report(conn=conn, end_day=day)
        except Exception as e:
            log_event("weekly_report_failed", error=str(e))

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        log_event(
            "run_end",
            run_id=run_id,
            run_type="ingest",
            status="ok",
            elapsed_ms=elapsed_ms,
            failures_by_code=failures,
            counts={
                "received": received,
                "after_dedupe": after_dedupe,
                "inserted": inserted,
                "duplicates": duplicates,
            },
        )

        print(f"OK day={day} run_id={run_id} received={received} inserted={inserted} failures={failures}")
        return 0

    except Exception as exc:
        # Unexpected error — mark run as failed
        finished_at = datetime.now(timezone.utc).isoformat()
        error_type = type(exc).__name__
        try:
            finish_run_error(
                conn,
                run_id=run_id,
                finished_at=finished_at,
                error_type=error_type,
                error_message=str(exc),
            )
            write_audit_log(conn, event_type="RUN_FINISHED_ERROR", ts=finished_at, run_id=run_id, day=day, details={"error_type": error_type, "error_message": str(exc)})
        except:
            pass
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        log_event(
            "run_end",
            run_id=run_id,
            run_type="ingest",
            status="error",
            elapsed_ms=elapsed_ms,
            failures_by_code=failures,
            error=str(exc),
        )
        print(f"ERROR day={day} run_id={run_id} error={exc}")
        return 1

    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

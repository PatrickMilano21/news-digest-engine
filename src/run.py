# src/run.py (additions only)
from __future__ import annotations

import os
from datetime import datetime, timezone
import uuid

from src.db import get_conn, init_db
from src.normalize import normalize_and_dedupe
from src.repo import insert_news_items, start_run, finish_run_ok, finish_run_error, get_latest_run
from src.rss_fetch import RSSFetchError, fetch_rss_with_retry
from src.rss_parse import RSSParseError, parse_rss

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = p.parse_args()

    # Validate input
    date.fromisoformat(args.date)

    # Create a run_id for this execution (stub)
    run_id = uuid.uuid4().hex

    # Structured log (stub)
    log_event("run_started", run_id=run_id, date=args.date)

    print(f"[RUN] date={args.date} run_id={run_id} status=ok (placeholder)")

    log_event("run_finished", run_id=run_id, date=args.date, status="ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

def run_rss_ingest(*, feed_specs: list[tuple[str, str]], mode: str, fixtures_dir: str) -> dict:
    run_id = uuid.uuid4().hex
    started_at = datetime.now(timezone.utc)

    conn = get_conn()
    try:
        init_db(conn)

        # We'll compute received after we parse (count of raw items before dedupe)
        start_run(conn, run_id, started_at, received=0)

        all_items = []
        try:
            for source_name, loc in feed_specs:
                if mode == "fixtures":
                    path = os.path.join(fixtures_dir, loc)
                    xml = open(path, "r", encoding="utf-8").read()
                elif mode == "prod":
                    xml = fetch_rss_with_retry(loc)
                else:
                    raise ValueError(f"unknown mode: {mode}")

                items = parse_rss(xml, source=source_name)
                all_items.extend(items)

            received = len(all_items)
            deduped = normalize_and_dedupe(all_items)
            after_dedupe = len(deduped)
            python_dupes = received - after_dedupe

            result = insert_news_items(conn, deduped)
            inserted = result["inserted"]
            db_ignored = result["duplicates"]
            duplicates = python_dupes + db_ignored

            finished_at = datetime.now(timezone.utc)
            finish_run_ok(
                conn,
                run_id,
                finished_at,
                after_dedupe=after_dedupe,
                inserted=inserted,
                duplicates=duplicates,
            )

            return {
                "run_id": run_id,
                "received": received,
                "after_dedupe": after_dedupe,
                "inserted": inserted,
                "duplicates": duplicates,
            }

        except RSSFetchError as exc:
            finished_at = datetime.now(timezone.utc)
            finish_run_error(conn, run_id, finished_at, error_type="RSS_FETCH_FAIL", error_message=str(exc))
            raise
        except RSSParseError as exc:
            finished_at = datetime.now(timezone.utc)
            finish_run_error(conn, run_id, finished_at, error_type="RSS_PARSE_FAIL", error_message=str(exc))
            raise

    finally:
        conn.close()
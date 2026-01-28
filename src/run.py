# src/run.py
from __future__ import annotations

import os
from datetime import datetime, timezone
import uuid

from src.db import get_conn, init_db
from src.normalize import normalize_and_dedupe
from src.repo import insert_news_items, start_run, finish_run_ok, finish_run_error
from src.rss_fetch import RSSFetchError, fetch_rss_with_retry
from src.rss_parse import RSSParseError, parse_rss


def run_rss_ingest(*, feed_specs: list[tuple[str, str]], mode: str, fixtures_dir: str) -> dict:
    run_id = uuid.uuid4().hex
    started_at = datetime.now(timezone.utc).isoformat()

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

            finished_at = datetime.now(timezone.utc).isoformat()
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
            finished_at = datetime.now(timezone.utc).isoformat()
            finish_run_error(conn, run_id, finished_at, error_type="RSS_FETCH_FAIL", error_message=str(exc))
            raise
        except RSSParseError as exc:
            finished_at = datetime.now(timezone.utc).isoformat()
            finish_run_error(conn, run_id, finished_at, error_type="RSS_PARSE_FAIL", error_message=str(exc))
            raise

    finally:
        conn.close()
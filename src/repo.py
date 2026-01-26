from __future__ import annotations

from datetime import datetime, timezone, timedelta
import sqlite3
import json


from src.schemas import NewsItem
from src.normalize import dedupe_key
from src.redact import sanitize

def insert_news_items(conn: sqlite3.Connection,items: list[NewsItem]) -> dict:
    inserted = 0
    duplicates = 0

    sql = """
    INSERT OR IGNORE INTO news_items
    (dedupe_key, source, url, published_at, title, evidence, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?);
    """
    for item in items:
        key = dedupe_key(str(item.url), item.title)
        created_at = datetime.now(timezone.utc).isoformat()
        published_at = item.published_at.isoformat()

        cur = conn.execute(
            sql,
            (
                key,
                item.source,
                str(item.url),
                published_at,
                item.title,
                item.evidence,
                created_at,
            ),
        )

        if cur.rowcount == 1:
            inserted += 1
        else:
            duplicates += 1

    conn.commit()
    return {"inserted": inserted, "duplicates": duplicates}


def start_run(conn: sqlite3.Connection, run_id: str, started_at: datetime, received: int, *, run_type: str = "ingest") -> None:
    conn.execute(
        """
        INSERT INTO runs (run_id, started_at, status, received, run_type)
        VALUES (?, ?, ?, ?, ?);
        """,
        (run_id, started_at, "started", received, run_type),
    )
    conn.commit()

def finish_run_ok(conn: sqlite3.Connection, run_id: str, finished_at: datetime, *, after_dedupe: int, inserted: int, duplicates: int) -> None:
    conn.execute(
        """
        UPDATE runs
        SET finished_at = ?, status = ?, after_dedupe = ?, inserted = ?, duplicates = ?
        WHERE run_id = ?
        """,
        (finished_at, "ok", after_dedupe, inserted, duplicates, run_id)
    )
    conn.commit()

def finish_run_error(conn: sqlite3.Connection, run_id: str, finished_at: datetime, *, error_type: str, error_message: str) -> None:
    conn.execute(
        """
        UPDATE runs
        SET finished_at = ?, status = ?, error_type = ?, error_message = ?
        WHERE run_id = ?
        """,
        (finished_at, "error", error_type, error_message, run_id)
    )
    conn.commit()


def get_latest_run(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute(
        """
        SELECT run_id, started_at, finished_at, status,
               received, after_dedupe, inserted, duplicates,
               error_type, error_message
        FROM runs
        ORDER BY started_at DESC
        LIMIT 1;
        """
    ).fetchone()

    if row is None:
        return None
    
    return {
        "run_id": row[0],
        "started_at": row[1],
        "finished_at": row[2],
        "status": row[3],
        "received": row[4],
        "after_dedupe": row[5],
        "inserted": row[6],
        "duplicates": row[7],
        "error_type": row[8],
        "error_message": row[9],
    }



def report_runs_by_day(conn: sqlite3.Connection, *, limit: int = 7) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
            substr(started_at, 1, 10) AS day,
            COUNT(*) AS runs,
            COALESCE(SUM(received), 0) AS received,
            COALESCE(SUM(inserted), 0) AS inserted,
            COALESCE(SUM(duplicates), 0) AS duplicates
        FROM runs
        GROUP BY day
        ORDER BY day DESC
        LIMIT ?;
        """,
        (limit,),
    ).fetchall()

    out: list[dict] = []
    for day, runs, received, inserted, duplicates in rows:
        out.append(
            {
                "day": day,
                "runs": runs,
                "received": received,
                "inserted": inserted,
                "duplicates": duplicates,
            }
        )
    return out


def get_news_items_by_date(conn: sqlite3.Connection, *, day: str) -> list[NewsItem]:
    rows = conn.execute(
        """
        SELECT source, url, published_at, title, evidence
        FROM news_items
        WHERE substr(published_at, 1, 10) = ?
        ORDER BY published_at DESC, id DESC;
        """,
        (day,),
    ).fetchall()

    out: list[NewsItem] = []
    for source, url, published_at, title, evidence in rows:
        out.append(
            NewsItem(
                source=source,
                url=url,
                published_at=datetime.fromisoformat(published_at),
                title=title,
                evidence=evidence,
            )
        )

    return out


def get_run_by_day(conn: sqlite3.Connection, *, day: str, run_type: str = "ingest") -> dict | None:
    """
    Read-only. Return the most recent run for a given YYYY-MM-DD day.

    Args:
        day: Date string in YYYY-MM-DD format
        run_type: Filter by run type ('ingest', 'eval'). Default 'ingest'.
    """
    row = conn.execute(
        """
        SELECT run_id, started_at, finished_at, status,
               received, after_dedupe, inserted, duplicates,
               error_type, error_message, run_type
        FROM runs
        WHERE substr(started_at, 1, 10) = ?
          AND run_type = ?
        ORDER BY started_at DESC
        LIMIT 1;
        """,
        (day, run_type),
    ).fetchone()

    if row is None:
        return None

    return {
        "run_id": row[0],
        "started_at": row[1],
        "finished_at": row[2],
        "status": row[3],
        "received": row[4],
        "after_dedupe": row[5],
        "inserted": row[6],
        "duplicates": row[7],
        "error_type": row[8],
        "error_message": row[9],
        "run_type": row[10],
    }


def has_successful_run_for_day(conn: sqlite3.Connection, *, day: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM runs
        WHERE substr(started_at, 1, 10) = ?
          AND status = 'ok'
        LIMIT 1;
        """,
        (day,),
    ).fetchone()

    return row is not None


def get_run_by_id(conn: sqlite3.Connection, *, run_id: str) -> dict | None:
    row = conn.execute(
        """
        SELECT run_id, started_at, finished_at, status,
            received, after_dedupe, inserted, duplicates,
            error_type, error_message, run_type,
            llm_cache_hits, llm_cache_misses, llm_total_cost_usd,
            llm_saved_cost_usd, llm_total_latency_ms
        FROM runs
        WHERE run_id = ?
        LIMIT 1;
        """,
        (run_id,),
    ).fetchone()

    if row is None:
        return None

    return {
        "run_id": row[0],
        "started_at": row[1],
        "finished_at": row[2],
        "status": row[3],
        "received": row[4],
        "after_dedupe": row[5],
        "inserted": row[6],
        "duplicates": row[7],
        "error_type": row[8],
        "error_message": row[9],
        "run_type": row[10],
        "llm_cache_hits": row[11] or 0,
        "llm_cache_misses": row[12] or 0,
        "llm_total_cost_usd": row[13] or 0.0,
        "llm_saved_cost_usd": row[14] or 0.0,
        "llm_total_latency_ms": row[15] or 0,
    }


def update_run_llm_stats(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    cache_hits: int,
    cache_misses: int,
    total_cost_usd: float,
    saved_cost_usd: float,
    total_latency_ms: int,
) -> None:
    """
    Update LLM statistics for a run.

    Called after digest generation completes.
    Idempotent: overwrites previous values if called again.
    """
    conn.execute(
        """
        UPDATE runs SET
            llm_cache_hits = ?,
            llm_cache_misses = ?,
            llm_total_cost_usd = ?,
            llm_saved_cost_usd = ?,
            llm_total_latency_ms = ?
        WHERE run_id = ?
        """,
        (cache_hits, cache_misses, total_cost_usd, saved_cost_usd, total_latency_ms, run_id),
    )
    conn.commit()


def upsert_run_failures(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    breakdown: dict[str, int],
    sources: dict[str, list[str]] | None = None,
) -> None:
    """Store failure counts and optionally the sources (URLs/paths) that failed.

    Args:
        breakdown: {error_code: count}
        sources: {error_code: [url1, url2, ...]} - optional, stores which feeds failed
    """
    conn.execute("DELETE FROM run_failures WHERE run_id = ?;", (run_id,))

    created_at = datetime.now(timezone.utc).isoformat()
    sources = sources or {}

    for error_code, count in breakdown.items():
        failed_sources = sources.get(error_code, [])
        failed_sources_json = json.dumps(failed_sources) if failed_sources else None
        conn.execute(
            """
            INSERT INTO run_failures (run_id, error_code, count, failed_sources, created_at)
            VALUES (?, ?, ?, ?, ?);
            """, (run_id, error_code, count, failed_sources_json, created_at)
        )

    conn.commit()


def get_run_failures_with_sources(conn: sqlite3.Connection, *, run_id: str) -> dict:
    """Get failure counts AND which sources failed.

    Returns:
        {
            "by_code": {"PARSE_ERROR": 1, "FETCH_ERROR": 2},
            "failed_sources": {"PARSE_ERROR": ["broken.xml"], "FETCH_ERROR": ["url1", "url2"]}
        }
    """
    rows = conn.execute(
        """
        SELECT error_code, count, failed_sources
        FROM run_failures
        WHERE run_id = ?;
        """,
        (run_id,),
    ).fetchall()

    by_code = {}
    failed_sources = {}
    for error_code, count, sources_json in rows:
        by_code[error_code] = count
        if sources_json:
            failed_sources[error_code] = json.loads(sources_json)

    return {"by_code": by_code, "failed_sources": failed_sources}


def insert_run_artifact(conn: sqlite3.Connection, *, run_id: str, kind: str, path: str) -> None:
    """
    Record an artifact produced by a run.
    Uses INSERT OR REPLACE so re-runs overwrite cleanly.
    """
    created_at = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT OR REPLACE INTO run_artifacts (run_id, kind, path, created_at)
        VALUES (?, ?, ?, ?);
        """,
        (run_id, kind, path, created_at),
    )
    conn.commit()

def get_run_artifacts(conn: sqlite3.Connection, *, run_id: str) -> dict[str, str]:
    """
    Retrieve artifacts for a run.
    Returns dict mapping kind to path, e.g., {"eval_report":"artifacts/eval_report_2026-01-18.md"}
    """
    rows = conn.execute(
        """
        SELECT kind, path
        FROM run_artifacts
        WHERE run_id = ?;
        """,
        (run_id,),
    ).fetchall()

    return{kind: path for kind, path in rows}
    

def get_news_item_by_id(conn: sqlite3.Connection, *, item_id: int) -> tuple[NewsItem, str] | None:     
    """Fetch a single news item by database ID. Returns (NewsItem, day) or None."""
    row = conn.execute(
        """
        SELECT source, url, published_at, title, evidence
        FROM news_items
        WHERE id = ?
        LIMIT 1;
        """,
        (item_id,),
    ).fetchone()

    if row is None:
        return None

    published_at = datetime.fromisoformat(row[2])
    day = published_at.date().isoformat()

    return NewsItem(
        source=row[0],
        url=row[1],
        published_at=published_at,
        title=row[3],
        evidence=row[4],
    ), day


def get_news_items_by_date_with_ids(conn: sqlite3.Connection, *, day: str) -> list[tuple[int, 
NewsItem]]:
    """Fetch items for a day with their database IDs for UI linking."""
    rows = conn.execute(
        """
        SELECT id, source, url, published_at, title, evidence
        FROM news_items
        WHERE substr(published_at, 1, 10) = ?
        ORDER BY published_at DESC, id DESC;
        """,
        (day,),
    ).fetchall()

    out: list[tuple[int, NewsItem]] = []
    for row in rows:
        item = NewsItem(
            source=row[1],
            url=row[2],
            published_at=datetime.fromisoformat(row[3]),
            title=row[4],
            evidence=row[5],
        )
        out.append((row[0], item))
    return out


def write_audit_log(conn: sqlite3.Connection, *, event_type: str, ts: datetime | str, run_id: str | None = None, day: str | None = None, details: dict | None = None) -> None:
    """Write an audit log entry. never raises - failures are swallowed."""
    try:
        ts_str = ts.isoformat() if isinstance(ts, datetime) else ts
        details_safe = sanitize(details  or {})
        conn.execute(
            """
            INSERT INTO audit_logs (ts, event_type, run_id, day, details_json)
            VALUES (?, ?, ?, ?, ?)
            """,(ts_str, event_type, run_id, day, json.dumps(details_safe))
        )
        conn.commit()
    except:
        pass # swallow errors

def get_audit_logs(conn: sqlite3.Connection, *, limit: int = 100) -> list[dict]:
    """Fetch recent audit logs for debugging."""
    rows = conn.execute(
        "SELECT id, ts, event_type, run_id, day, details_json FROM audit_logs ORDER BY id DESC LIMIT ?",   
        (limit,)
    ).fetchall()
    return [
        {
            "id": r[0],
            "ts": r[1],
            "event_type": r[2],
            "run_id": r[3],
            "day": r[4],
            "details": json.loads(r[5]) if r[5] else {}
        }
        for r in rows
    ]


def report_top_sources(conn: sqlite3.Connection, *, end_day: str, days: int = 7, limit: int = 10) -> list[dict]:
    """Get top sources by item count over the last N days."""
    end_date = datetime.strptime(end_day, "%Y-%m-%d").date()
    start_date = end_date - timedelta(days=days - 1)
    start_day = start_date.isoformat()
    

    rows = conn.execute(
        """
        SELECT source, COUNT(*) as count
        FROM news_items
        WHERE DATE(published_at) BETWEEN ? AND ?
        GROUP BY source
        ORDER BY count DESC
        LIMIT ?
        """,(start_day, end_day, limit)
    ).fetchall()

    return [{"source": row[0], "count": row[1]} for row in rows]


def report_failures_by_code(conn: sqlite3.Connection, *, end_day: str, days: int = 7) -> dict[str, int]:
    """Get run failure counts by error_type over the last N days."""
    end_date = datetime.strptime(end_day, "%Y-%m-%d").date()
    start_date = end_date - timedelta(days=days - 1)
    start_day = start_date.isoformat()

    rows = conn.execute(
        """
        SELECT error_type, COUNT(*)
        FROM runs
        WHERE status = 'error'
        AND DATE(started_at) BETWEEN ? AND ?
        AND error_type IS NOT NULL
        GROUP BY error_type
        """,
        (start_day, end_day)
    ).fetchall()

    return {row[0]: row[1] for row in rows}


def get_cached_summary(conn: sqlite3.Connection, *, cache_key: str) -> dict | None:
    """
    Look up a cached LLM summary by cache key.

    Args:
        conn: database connection
        cache_key: SHA-256 hash of (model|evidence)

    Returns:
        dict with all cache columns if found, None if not found
    """
    cur = conn.execute(
        """
        SELECT cache_key, model_name, summary_json, prompt_tokens,
        completion_tokens, cost_usd, latency_ms, created_at
        FROM summary_cache
        WHERE cache_key = ?
        """, (cache_key,)
    )
    row = cur.fetchone()
    if row is None:
        return None
    return {
        "cache_key": row[0],
        "model_name": row[1],
        "summary_json": row[2],
        "prompt_tokens": row[3],
        "completion_tokens": row[4],
        "cost_usd": row[5],
        "latency_ms": row[6],
        "created_at": row[7],
    }

def insert_cached_summary(conn: sqlite3.Connection, *, cache_key: str, model_name: str, summary_json: str,
    prompt_tokens: int, completion_tokens: int, cost_usd: float, latency_ms: int, created_at: str) -> None:
    """
    Store a summary in the cache.
    
    Uses INSERT OR IGNORE for idempotency — if cache_key exists,
    this is a no-op (first write wins, cache entries are immutable).
    
    Args:
        conn: Database connection
        cache_key: SHA-256 hash of (model|evidence)
        model_name: LLM model name (e.g., "gpt-4o-mini")
        summary_json: Serialized SummaryResult
        prompt_tokens: Token count from original call
        completion_tokens: Token count from original call
        cost_usd: Cost of original call
        latency_ms: Latency of original call
        created_at: ISO 8601 timestamp
    """
    conn.execute(
        """
        INSERT OR IGNORE INTO summary_cache
        (cache_key, model_name, summary_json, prompt_tokens, completion_tokens, cost_usd,
         latency_ms, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,(cache_key, model_name, summary_json, prompt_tokens,
           completion_tokens, cost_usd, latency_ms, created_at)
    )
    conn.commit()

def get_idempotency_response(conn: sqlite3.Connection, *, key: str) -> dict | None:
    """Return cached response if idempotency key exists, else None."""
    cur = conn.execute(
        "SELECT key, endpoint, response_json, created_at FROM idempotency_keys WHERE key = ?",
        (key,)
    )
    row = cur.fetchone()
    if row is None:
        return None 
    return {
        "key": row[0],
        "endpoint": row[1],
        "response_json": row[2],
        "created_at": row[3]
    }

def store_idempotency_response(conn: sqlite3.Connection, *, key: str, endpoint: str,
                               response_json: str, created_at: str) -> None:
    """Store response for idempotency key. INSERT OR IGNORE for safety."""
    conn.execute(
        """INSERT OR IGNORE INTO idempotency_keys (key, endpoint, response_json, created_at)
           VALUES (?, ?, ?, ?)""",
        (key, endpoint, response_json, created_at)
    )
    conn.commit()


def upsert_run_feedback(conn: sqlite3.Connection, *, run_id: str, rating: int, comment: str | None,
                        created_at: str, updated_at: str) -> int:
    """
    Insert or update feedback for a run (overall digest rating).

    - First submit for run_id → INSERT new row
    - Submit again for same run_id → UPDATE existing row

    Returns:
        feedback_id of the inserted/updated row
    """

    # Try INSERT first
    cur = conn.execute(
        """INSERT INTO run_feedback (run_id, rating, comment, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                rating = excluded.rating,
                comment = excluded.comment,
                updated_at = excluded.updated_at
            RETURNING feedback_id""",
        (run_id, rating, comment, created_at, updated_at)
    )
    row = cur.fetchone()
    conn.commit()
    return row[0]



def upsert_item_feedback(conn: sqlite3.Connection, *, run_id: str, item_url: str, useful: int,
                         created_at: str, updated_at: str) -> int:
    """
    Insert or update feedback for a specific item in a run.

    - First submit for (run_id, item_url) → INSERT new row
    - Submit again for same pair → UPDATE existing row

    Args:
        useful: 1 = useful (thumbs up), 0 = not useful (thumbs down)

    Returns:
        feedback_id of the inserted/updated row
    """
    cur = conn.execute(
        """INSERT INTO item_feedback (run_id, item_url, useful, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(run_id, item_url) DO UPDATE SET
               useful = excluded.useful,
               updated_at = excluded.updated_at
           RETURNING feedback_id""",
        (run_id, item_url, useful, created_at, updated_at)
    )
    row = cur.fetchone()
    conn.commit()
    return row[0]


def get_distinct_dates(conn: sqlite3.Connection, *, limit: int | None = None, offset: int = 0) -> list[str]:
    """Get distinct dates that have news items, ordered descending.

    Args:
        limit: Max dates to return (None = all)
        offset: Skip first N dates (for pagination)

    Returns:
        List of YYYY-MM-DD strings
    """
    if limit is not None:
        rows = conn.execute(
            "SELECT DISTINCT substr(published_at, 1, 10) as day FROM news_items ORDER BY day DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT DISTINCT substr(published_at, 1, 10) as day FROM news_items ORDER BY day DESC"
        ).fetchall()
    return [row[0] for row in rows]


def count_distinct_dates(conn: sqlite3.Connection) -> int:
    """Count total distinct dates with news items."""
    return conn.execute(
        "SELECT COUNT(DISTINCT substr(published_at, 1, 10)) FROM news_items"
    ).fetchone()[0]


def count_items_for_dates(conn: sqlite3.Connection, *, dates: list[str]) -> int:
    """Count total news items for a list of dates."""
    if not dates:
        return 0
    placeholders = ",".join("?" * len(dates))
    return conn.execute(
        f"SELECT COUNT(*) FROM news_items WHERE substr(published_at, 1, 10) IN ({placeholders})",
        dates
    ).fetchone()[0]


def count_runs_for_dates(conn: sqlite3.Connection, *, dates: list[str]) -> int:
    """Count total runs for a list of dates."""
    if not dates:
        return 0
    placeholders = ",".join("?" * len(dates))
    return conn.execute(
        f"SELECT COUNT(*) FROM runs WHERE substr(started_at, 1, 10) IN ({placeholders})",
        dates
    ).fetchone()[0]


def get_items_count_by_date(conn: sqlite3.Connection, *, dates: list[str]) -> list[dict]:
    """Get item count breakdown for each date.

    Returns:
        [{"date": "2026-01-25", "items": 150}, ...]
    """
    result = []
    for day in dates:
        count = conn.execute(
            "SELECT COUNT(*) FROM news_items WHERE substr(published_at, 1, 10) = ?",
            (day,)
        ).fetchone()[0]
        result.append({"date": day, "items": count})
    return result


def get_recent_runs_summary(conn: sqlite3.Connection, *, limit: int = 10) -> list[dict]:
    """Get recent runs with basic info for display.

    Returns:
        [{"run_id": "...", "day": "2026-01-25", "status": "ok",
          "run_type": "ingest", "received": 150, "inserted": 140}, ...]
    """
    rows = conn.execute(
        """SELECT run_id, substr(started_at, 1, 10) as day, status, run_type, received, inserted
           FROM runs ORDER BY started_at DESC LIMIT ?""",
        (limit,)
    ).fetchall()
    return [
        {"run_id": r[0], "day": r[1], "status": r[2], "run_type": r[3], "received": r[4], "inserted": r[5]}
        for r in rows
    ]


def get_run_feedback(conn: sqlite3.Connection, *, run_id: str) -> dict | None:
    """Get feedback for a run, if it exists."""
    cur = conn.execute(
        """SELECT feedback_id, run_id, rating, comment, created_at, updated_at
           FROM run_feedback WHERE run_id = ?""",
        (run_id,)
    )
    row = cur.fetchone()
    if row is None:
        return None
    return {
        "feedback_id": row[0],
        "run_id": row[1],
        "rating": row[2],
        "comment": row[3],
        "created_at": row[4],
        "updated_at": row[5],
    }


def get_item_feedback(conn: sqlite3.Connection, *, run_id: str, item_url: str) -> dict | None:
    """Get feedback for a specific item in a run, if it exists."""
    cur = conn.execute(
        """SELECT feedback_id, run_id, item_url, useful, created_at, updated_at
           FROM item_feedback WHERE run_id = ? AND item_url = ?""",
        (run_id, item_url)
    )
    row = cur.fetchone()
    if row is None:
        return None
    return {
        "feedback_id": row[0],
        "run_id": row[1],
        "item_url": row[2],
        "useful": row[3],
        "created_at": row[4],
        "updated_at": row[5],
    }



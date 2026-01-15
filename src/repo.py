from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

from src.schemas import NewsItem, dedupe_key


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


def start_run(conn: sqlite3.Connection, run_id: str, started_at: datetime, received: int) -> None:
    conn.execute(
        """
        INSERT INTO runs (run_id, started_at, status, received)
        VALUES (?, ?, ?, ?);
        """,
        (run_id, started_at, "started", received),
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


def get_run_by_day(conn: sqlite3.Connection, *, day: str) -> dict | None:
    """
    Read-only. Return the most recent run row for a given YYYY-MM-DD day
    based on started_at's first 10 chars (ISO date).
    """
    row = conn.execute(
        """
        SELECT run_id, started_at, finished_at, status,
               received, after_dedupe, inserted, duplicates,
               error_type, error_message
        FROM runs
        WHERE substr(started_at, 1, 10) = ?
        ORDER BY started_at DESC
        LIMIT 1;
        """,
        (day,),
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

def has_successful_run_for_day(conn, *, day: str) -> bool:
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

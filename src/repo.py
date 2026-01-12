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


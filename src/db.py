from __future__ import annotations

import os
import sqlite3
from pathlib import Path





def get_conn() -> sqlit3.Connection:
    """
    Open a SQLite connection to the DB path. 
    DB path is configured via NEWS_DB_PATH env var, with a safe local default.
    """
    db_path = os.environ.get("NEWS_DB_PATH", "./data/news.db")
    path = Path(db_path)

    # Ensure parent directory exists (e.g., ./data/)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    return conn


def init_db(conn: sqlit3.Connection) -> None:
    """
    Create required tables if they don't exist.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS news_items (
            id INTEGER PRIMARY KEY,
            dedupe_key TEXT NOT NULL UNIQUE,
            source TEXT NOT NULL,
            url TEXT NOT NULL,
            published_at TEXT NOT NULL,
            title TEXT NOT NULL,
            evidence TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()
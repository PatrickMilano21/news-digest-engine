# src/db.py
from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def get_conn() -> sqlite3.Connection:
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


def init_db(conn: sqlite3.Connection) -> None:
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

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            received INTEGER NOT NULL DEFAULT 0,
            after_dedupe INTEGER NOT NULL DEFAULT 0,
            inserted INTEGER NOT NULL DEFAULT 0,
            duplicates INTEGER NOT NULL DEFAULT 0,
            error_type TEXT,
            error_message TEXT,
            run_type TEXT NOT NULL DEFAULT 'ingest'
        );
        """
    )

    conn.execute(
         """
        CREATE TABLE IF NOT EXISTS run_failures (     
              id INTEGER PRIMARY KEY,
              run_id TEXT NOT NULL,
              error_code TEXT NOT NULL,
              count INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL
        );
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS run_artifacts (
            id INTEGER PRIMARY KEY,
            run_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            path TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(run_id, kind)
        );
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            event_type TEXT NOT NULL,
            run_id TEXT,
            day TEXT,
            details_json TEXT
        )
        """
    )
    # summary_cache table - LLM summary caching (Day 17)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS summary_cache (
            cache_key TEXT PRIMARY KEY,
            model_name TEXT NOT NULL,
            summary_json TEXT NOT NULL,
            prompt_tokens INTEGER NOT NULL,
            completion_tokens INTEGER NOT NULL,
            cost_usd REAL NOT NULL,
            latency_ms INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
    """
    )

    # idempotency_keys table - prevents duplicate HTTP requests (Day 18)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS idempotency_keys (
            id INTEGER PRIMARY KEY,
            key TEXT NOT NULL UNIQUE,
            endpoint TEXT NOT NULL,
            response_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # run_feedback table - overall digest rating (Day 18)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS run_feedback (
            feedback_id INTEGER PRIMARY KEY,
            run_id TEXT NOT NULL UNIQUE,
            rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
            comment TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # item_feedback table - per-item usefulness rating (Day 18)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS item_feedback (
            feedback_id INTEGER PRIMARY KEY,
            run_id TEXT NOT NULL,
            item_url TEXT NOT NULL,
            useful INTEGER NOT NULL CHECK (useful IN (0, 1)),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(run_id, item_url)
        )
    """)

    conn.commit()

    # Idempotent migration: add run_type column if missing (for existing DBs)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(runs);").fetchall()]
    if "run_type" not in cols:
        conn.execute("ALTER TABLE runs ADD COLUMN run_type TEXT NOT NULL DEFAULT 'ingest';")
        conn.commit()

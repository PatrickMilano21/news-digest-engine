# src/db.py
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class InvalidDbPathError(Exception):
    """Raised when NEWS_DB_PATH points to an invalid location."""
    pass


@contextmanager
def db_conn():
    """
    Context manager for database connections.
    Opens connection, initializes schema, yields connection, closes on exit.

    Usage:
        with db_conn() as conn:
            # use conn
    """
    conn = get_conn()
    try:
        init_db(conn)
        yield conn
    finally:
        conn.close()


def get_conn() -> sqlite3.Connection:
    """
    Open a SQLite connection to the DB path.
    DB path is configured via NEWS_DB_PATH env var, with a safe local default.
    """
    db_path = os.environ.get("NEWS_DB_PATH", "./data/news.db")
    path = Path(db_path)

    # Validate: if NEWS_DB_PATH is set, check that the root/drive exists
    if os.environ.get("NEWS_DB_PATH"):
        # Get the root of the path (e.g., "Z:\" on Windows, "/" on Unix)
        root = path.anchor or path.parts[0] if path.parts else None
        if root and not Path(root).exists():
            raise InvalidDbPathError(
                f"NEWS_DB_PATH is set to '{db_path}' but the root path '{root}' doesn't exist.\n"
                f"Fix: Clear the env var with: $env:NEWS_DB_PATH = $null"
            )

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
            run_type TEXT NOT NULL DEFAULT 'ingest',
            llm_cache_hits INTEGER DEFAULT 0,
            llm_cache_misses INTEGER DEFAULT 0,
            llm_total_cost_usd REAL DEFAULT 0.0,
            llm_saved_cost_usd REAL DEFAULT 0.0,
            llm_total_latency_ms INTEGER DEFAULT 0
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
              failed_sources TEXT,
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

    # weight_snapshots table - source weight learning loop (Milestone 3b)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS weight_snapshots (
            snapshot_id INTEGER PRIMARY KEY,
            cycle_date TEXT NOT NULL,
            user_id TEXT,
            config_version INTEGER NOT NULL DEFAULT 1,
            weights_before TEXT NOT NULL,
            weights_after TEXT NOT NULL,
            feedback_summary TEXT NOT NULL,
            eval_pass_rate_before REAL,
            eval_pass_rate_after REAL,
            applied INTEGER NOT NULL DEFAULT 0,
            rejected_reason TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(cycle_date, user_id)
        )
    """)

    # users table - Milestone 4 (Multi-User)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL,
            last_login_at TEXT
        )
    """)

    # user_configs table - per-user ranking config overrides (Milestone 4)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_configs (
            config_id INTEGER PRIMARY KEY,
            user_id TEXT NOT NULL UNIQUE,
            config_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # sessions table - server-side session management (Milestone 4)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # config_suggestions table - AI advisor suggestions (Milestone 4.5)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS config_suggestions (
            suggestion_id INTEGER PRIMARY KEY,
            user_id TEXT NOT NULL,
            suggestion_type TEXT NOT NULL,
            field TEXT NOT NULL,
            target_key TEXT,
            current_value TEXT,
            suggested_value TEXT NOT NULL,
            evidence_items TEXT NOT NULL,
            evidence_count INTEGER NOT NULL,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            resolved_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # Idempotent migration: add target_key column if missing (for existing DBs)
    try:
        conn.execute("ALTER TABLE config_suggestions ADD COLUMN target_key TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # suggestion_outcomes table - rich snapshots for learning (Milestone 4.5)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS suggestion_outcomes (
            outcome_id INTEGER PRIMARY KEY,
            suggestion_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            suggestion_type TEXT NOT NULL,
            suggestion_value TEXT NOT NULL,
            outcome TEXT NOT NULL,
            user_reason TEXT,
            config_before TEXT,
            config_after TEXT,
            evidence_summary TEXT,
            created_at TEXT NOT NULL,
            decided_at TEXT,
            FOREIGN KEY (suggestion_id) REFERENCES config_suggestions(suggestion_id)
        )
    """)

    # user_preference_profiles table - computed patterns (Milestone 4.5)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_preference_profiles (
            profile_id INTEGER PRIMARY KEY,
            user_id TEXT NOT NULL UNIQUE,
            acceptance_stats TEXT NOT NULL,
            patterns TEXT NOT NULL,
            trends TEXT,
            total_outcomes INTEGER DEFAULT 0,
            last_outcome_at TEXT,
            computed_at TEXT NOT NULL
        )
    """)

    # Indexes for config_suggestions (Milestone 4.5)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_suggestions_user
        ON config_suggestions(user_id, status)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_outcomes_user
        ON suggestion_outcomes(user_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_outcomes_type
        ON suggestion_outcomes(suggestion_type, outcome)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_outcomes_date
        ON suggestion_outcomes(created_at)
    """)

    conn.commit()

    # Idempotent migration: add run_type column if missing (for existing DBs)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(runs);").fetchall()]
    if "run_type" not in cols:
        conn.execute("ALTER TABLE runs ADD COLUMN run_type TEXT NOT NULL DEFAULT 'ingest';")
        conn.commit()

    # Idempotent migration: add LLM stats columns if missing (Day 20)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(runs);").fetchall()]
    if "llm_cache_hits" not in cols:
        conn.execute("ALTER TABLE runs ADD COLUMN llm_cache_hits INTEGER DEFAULT 0;")
        conn.execute("ALTER TABLE runs ADD COLUMN llm_cache_misses INTEGER DEFAULT 0;")
        conn.execute("ALTER TABLE runs ADD COLUMN llm_total_cost_usd REAL DEFAULT 0.0;")
        conn.execute("ALTER TABLE runs ADD COLUMN llm_saved_cost_usd REAL DEFAULT 0.0;")
        conn.execute("ALTER TABLE runs ADD COLUMN llm_total_latency_ms INTEGER DEFAULT 0;")
        conn.commit()

    # Idempotent migration: add failed_sources column to run_failures if missing
    cols = [row[1] for row in conn.execute("PRAGMA table_info(run_failures);").fetchall()]
    if "failed_sources" not in cols:
        conn.execute("ALTER TABLE run_failures ADD COLUMN failed_sources TEXT;")
        conn.commit()

    # Idempotent migration: add suggested_tags column to news_items (Milestone 3a)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(news_items);").fetchall()]
    if "suggested_tags" not in cols:
        conn.execute("ALTER TABLE news_items ADD COLUMN suggested_tags TEXT;")
        conn.commit()

    # Idempotent migration: add reason_tag column to item_feedback (Milestone 3a)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(item_feedback);").fetchall()]
    if "reason_tag" not in cols:
        conn.execute("ALTER TABLE item_feedback ADD COLUMN reason_tag TEXT;")
        conn.commit()

    # Idempotent migration: add user_id column to runs (Milestone 4)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(runs);").fetchall()]
    if "user_id" not in cols:
        conn.execute("ALTER TABLE runs ADD COLUMN user_id TEXT;")
        conn.commit()

    # Idempotent migration: add user_id column to item_feedback (Milestone 4)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(item_feedback);").fetchall()]
    if "user_id" not in cols:
        conn.execute("ALTER TABLE item_feedback ADD COLUMN user_id TEXT;")
        conn.commit()

    # Idempotent migration: add user_id column to run_feedback (Milestone 4)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(run_feedback);").fetchall()]
    if "user_id" not in cols:
        conn.execute("ALTER TABLE run_feedback ADD COLUMN user_id TEXT;")
        conn.commit()

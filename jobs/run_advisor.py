"""
Scheduled job: Run the Config Advisor Agent for one or all users.

Usage:
    python -m jobs.run_advisor --user-id UUID          # Single user, respects 7-day window
    python -m jobs.run_advisor --user-id UUID --force   # Single user, skip 7-day (still 1/day)
    python -m jobs.run_advisor --all-users              # All users, pre-filter + 7-day window
    python -m jobs.run_advisor --all-users --force       # All users, pre-filter + skip 7-day
"""
from dotenv import load_dotenv
load_dotenv()

import argparse
import sys
from datetime import date, datetime, timedelta, timezone

from src.advisor import run_advisor, OPENAI_API_KEY
from src.advisor_tools import query_user_feedback
from src.db import get_conn, init_db
from src.logging_utils import log_event
from src.repo import get_all_users, get_suggestions_for_today


def _ran_recently(conn, user_id: str, days: int = 7) -> bool:
    """Check if the advisor ran for this user within the last N days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    row = conn.execute(
        """
        SELECT 1 FROM runs
        WHERE user_id = ? AND run_type = 'advisor' AND started_at >= ?
        LIMIT 1
        """,
        (user_id, cutoff),
    ).fetchone()
    return row is not None


def _has_sufficient_data(conn, user_id: str) -> bool:
    """Quick check if user has enough feedback for the advisor."""
    result = query_user_feedback(conn, user_id=user_id)
    return not result.get("insufficient_data", True)


def _already_generated_today(conn, user_id: str) -> bool:
    """Check if suggestions were already created today for this user."""
    today = date.today().isoformat()
    existing = get_suggestions_for_today(conn, user_id=user_id, day=today)
    return bool(existing)


def run_for_user(conn, user_id: str, *, force: bool = False) -> dict:
    """Run advisor for a single user with all checks."""
    # Check: already generated today (1/day limit)
    if _already_generated_today(conn, user_id):
        log_event("advisor_job_skip", user_id=user_id, reason="already_generated_today")
        print(f"  SKIP {user_id}: already generated today")
        return {"status": "already_generated"}

    # Check: ran within 7 days (unless --force)
    if not force and _ran_recently(conn, user_id):
        log_event("advisor_job_skip", user_id=user_id, reason="ran_within_7_days")
        print(f"  SKIP {user_id}: ran within 7 days (use --force to override)")
        return {"status": "skipped_recent"}

    # Check: sufficient data
    if not _has_sufficient_data(conn, user_id):
        log_event("advisor_job_skip", user_id=user_id, reason="insufficient_data")
        print(f"  SKIP {user_id}: insufficient feedback data")
        return {"status": "skipped_data"}

    # Run the advisor
    print(f"  RUNNING advisor for {user_id}...")
    result = run_advisor(user_id, conn)
    print(f"  RESULT: {result.get('status')} — {result.get('suggestions_created', 0)} suggestions")
    return result


def main() -> int:
    p = argparse.ArgumentParser(description="Run Config Advisor Agent")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--user-id", help="Run for specific user UUID")
    group.add_argument("--all-users", action="store_true", help="Run for all users")
    p.add_argument("--force", action="store_true", help="Skip 7-day window (still 1/day)")
    args = p.parse_args()

    if not OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY not set")
        return 1

    conn = get_conn()
    init_db(conn)

    try:
        if args.user_id:
            print(f"Config Advisor — single user: {args.user_id}")
            result = run_for_user(conn, args.user_id, force=args.force)
            return 0 if result.get("status") in ("completed", "already_generated", "skipped_recent", "skipped_data") else 1

        if args.all_users:
            users = get_all_users(conn)
            print(f"Config Advisor — {len(users)} users (force={args.force})")

            results = {"completed": 0, "skipped": 0, "errors": 0}
            for user in users:
                uid = user["user_id"]
                result = run_for_user(conn, uid, force=args.force)
                status = result.get("status", "")
                if status == "completed":
                    results["completed"] += 1
                elif status.startswith("skipped") or status == "already_generated":
                    results["skipped"] += 1
                else:
                    results["errors"] += 1

            print(f"\nSummary: {results['completed']} completed, {results['skipped']} skipped, {results['errors']} errors")
            return 0

    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

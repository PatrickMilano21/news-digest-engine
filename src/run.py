import argparse
import uuid
from datetime import date

from src.logging_utils import log_event


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

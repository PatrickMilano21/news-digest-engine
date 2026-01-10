import argparse
import uuid
from datetime import date

from src.logging_utils import log_event


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = p.parse_args()

    date.fromisoformat(args.date)

    run_id = uuid.uuid4().hex

    log_event("eval_started", run_id=run_id, date=args.date)

    print(f"[EVAL] date={args.date} run_id={run_id} score=1.00 (placeholder)")

    log_event("eval_finished", run_id=run_id, date=args.date, score=1.00)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

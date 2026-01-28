import argparse
import time
import uuid
from datetime import date, datetime, timezone

from src.logging_utils import log_event
from src.db import get_conn, init_db
from src.repo import upsert_run_failures, start_run, finish_run_ok, insert_run_artifact
from evals.runner import run_all, write_eval_report
from evals.summary_runner import run_all_cases as run_summary_cases, summarize_results as summarize_summary_results


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = p.parse_args()

    # Validate date format
    date.fromisoformat(args.date)
    day = args.date

    run_id = uuid.uuid4().hex
    t0 = time.perf_counter()
    log_event("eval_started", run_id=run_id, date=day)

    # Create timestamp for eval (end of the given day)
    now = datetime.combine(date.fromisoformat(day), datetime.max.time(), tzinfo=timezone.utc)

    conn = get_conn()
    try:
        init_db(conn)

        # 1. Create run record
        started_at = datetime.now(timezone.utc).isoformat()
        start_run(conn, run_id=run_id, started_at=started_at, received=0, run_type='eval')
        # 2. Run all eval cases
        out = run_all(now=now)
        # 3. Extract stats
        total = out["total"]
        passed = out["passed"]
        failed = out["failed"]
        pass_rate = passed / total if total > 0 else 0.0
        # 4. Build failure breakdown
        breakdown = {}
        for r in out["results"]:
            if not r["pass"]:
                code = r.get("error_code") or "UNKNOWN"
                breakdown[code] = breakdown.get(code, 0) + 1
        # 5. Mark run complete
        finished_at = datetime.now(timezone.utc).isoformat()
        finish_run_ok(conn, run_id=run_id, finished_at=finished_at, after_dedupe=total, inserted=passed, duplicates=failed,)

        # 6. Store breakdown in DB
        upsert_run_failures(conn, run_id=run_id, breakdown=breakdown)

        # 7. Write eval report artifact
        report_path = write_eval_report(out, day=day, run_id=run_id)

        # 8. Record artifact in DB
        insert_run_artifact(conn, run_id=run_id, kind="eval_report", path=report_path)

        # 9. Run summary quality evals for console output
        summary_results = run_summary_cases()
        summary_stats = summarize_summary_results(summary_results)

        # 10. Calculate combined totals
        combined_total = total + summary_stats["total"]
        combined_passed = passed + summary_stats["passed"]
        combined_rate = (combined_passed / combined_total * 100) if combined_total > 0 else 0.0

        # 11. Print and log
        print(f"[EVAL] date={day} run_id={run_id}")
        print(f"[EVAL] ranking: {pass_rate:.2%} ({passed}/{total})")
        print(f"[EVAL] summary: {summary_stats['pass_rate']}% ({summary_stats['passed']}/{summary_stats['total']})")
        print(f"[EVAL] overall: {combined_rate:.1f}% ({combined_passed}/{combined_total})")
        print(f"[EVAL] report written to {report_path}")

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        log_event(
            "run_end",
            run_id=run_id,
            run_type="eval",
            status="ok",
            elapsed_ms=elapsed_ms,
            failures_by_code=breakdown,
            counts={
                "ranking_total": total,
                "ranking_passed": passed,
                "ranking_failed": failed,
                "summary_total": summary_stats["total"],
                "summary_passed": summary_stats["passed"],
                "summary_failed": summary_stats["failed"],
            },
            artifact_paths={"eval_report": report_path},
        )        

        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
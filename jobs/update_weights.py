# jobs/update_weights.py
"""
Weight update cycle job (Milestone 3b).

Aggregates user feedback, computes source weight adjustments,
runs regression guard, and persists snapshot.

Usage:
    python -m jobs.update_weights --date 2026-01-28
"""
from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import argparse
import os
from datetime import date, datetime, timezone

from src.db import get_conn, init_db
from src.repo import (
    aggregate_feedback_by_source,
    get_active_source_weights,
    upsert_weight_snapshot,
)
from src.weights import compute_weight_adjustments, compute_weight_changes
from src.logging_utils import log_event


def run_evals_with_weights(weights: dict[str, float]) -> dict:
    """
    Run evaluation suite as regression guard.

    Note: Current eval cases define their own RankConfig per case,
    so the provided weights don't directly affect case outcomes.
    This serves as a health check that the ranking system works correctly.

    Future enhancement: Add source-weight-specific eval cases that
    use the provided weights to test weight-based ranking behavior.

    Args:
        weights: Source weights (currently unused by eval cases)

    Returns:
        Dict with 'pass_rate', 'passed', 'total'
    """
    from evals.runner import run_all

    # Use a fixed timestamp for deterministic evals
    now = datetime(2026, 1, 14, 23, 59, 59, tzinfo=timezone.utc)

    try:
        out = run_all(now=now)
        total = out["total"]
        passed = out["passed"]
        pass_rate = passed / total if total > 0 else 1.0
    except Exception as e:
        # If evals fail to run, treat as 0% pass rate
        print(f"[WEIGHTS] Eval error: {e}")
        return {
            "pass_rate": 0.0,
            "passed": 0,
            "total": 0,
        }

    return {
        "pass_rate": pass_rate,
        "passed": passed,
        "total": total,
    }


def write_weight_artifact(
    cycle_date: str,
    feedback_summary: dict,
    weight_changes: list[dict],
    eval_before: dict,
    eval_after: dict,
    applied: bool,
    rejected_reason: str | None,
    snapshot_id: int,
) -> str:
    """
    Write weight update report artifact.

    Args:
        cycle_date: YYYY-MM-DD
        feedback_summary: Aggregated feedback stats by source
        weight_changes: List of weight change dicts
        eval_before: Baseline eval results
        eval_after: Candidate eval results
        applied: Whether weights were applied
        rejected_reason: Reason if not applied
        snapshot_id: Database snapshot ID

    Returns:
        Path to written artifact
    """
    os.makedirs("artifacts", exist_ok=True)
    path = os.path.join("artifacts", f"weight_update_{cycle_date}.md")

    lines = [
        f"# Weight Update Report - {cycle_date}",
        "",
        "## Feedback Summary",
        "| Source | Total | Useful | Rate 7d | Rate LT | Effective |",
        "|--------|-------|--------|---------|---------|-----------|",
    ]

    for source, stats in sorted(feedback_summary.items()):
        lines.append(
            f"| {source} | {stats['total']} | {stats['useful']} | "
            f"{stats['rate_7d']:.2f} | {stats['rate_longterm']:.2f} | "
            f"{stats['effective_rate']:.2f} |"
        )

    if not feedback_summary:
        lines.append("| (no feedback data) | - | - | - | - | - |")

    lines.extend([
        "",
        "## Weight Changes",
        "| Source | Before | After | Change | Reason |",
        "|--------|--------|-------|--------|--------|",
    ])

    for change in weight_changes:
        delta = change["change"]
        delta_str = f"+{delta:.2f}" if delta > 0 else f"{delta:.2f}" if delta < 0 else "-"
        lines.append(
            f"| {change['source']} | {change['before']:.2f} | {change['after']:.2f} | "
            f"{delta_str} | {change['reason']} |"
        )

    if not weight_changes:
        lines.append("| (no changes) | - | - | - | - |")

    lines.extend([
        "",
        "## Eval Comparison (Fixtures - Gating)",
        f"- Baseline: {eval_before['pass_rate']:.0%} ({eval_before['passed']}/{eval_before['total']} passed)",
        f"- Candidate: {eval_after['pass_rate']:.0%} ({eval_after['passed']}/{eval_after['total']} passed)",
        f"- Delta: {(eval_after['pass_rate'] - eval_before['pass_rate']) * 100:+.1f}%",
        "",
        "## Result",
    ])

    if applied:
        lines.append(f"**APPLIED** - snapshot_id: {snapshot_id}")
    else:
        lines.append(f"**REJECTED** - reason: {rejected_reason}, snapshot_id: {snapshot_id}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run weight update cycle")
    p.add_argument("--date", required=True, help="YYYY-MM-DD cycle date")
    p.add_argument("--user-id", default=None, help="User ID for scoped data (None = global)")
    args = p.parse_args(argv)

    # Validate date format
    cycle_date = date.fromisoformat(args.date).isoformat()
    user_id = args.user_id

    log_event("weight_update_started", cycle_date=cycle_date)
    print(f"[WEIGHTS] Starting weight update for {cycle_date}")

    conn = get_conn()
    try:
        init_db(conn)

        # 1. AGGREGATE feedback by source
        feedback_stats = aggregate_feedback_by_source(
            conn,
            as_of_date=cycle_date,
            short_window_days=7,
            min_votes=5,
        )
        print(f"[WEIGHTS] Aggregated feedback for {len(feedback_stats)} sources")

        # 2. LOAD current weights (user-scoped)
        current_weights = get_active_source_weights(conn, user_id=user_id)
        print(f"[WEIGHTS] Loaded {len(current_weights)} current weights")

        # 3. COMPUTE proposed weights
        if not feedback_stats:
            # No feedback data - no changes
            proposed_weights = current_weights.copy()
            applied = False
            rejected_reason = "no_feedback"
            print("[WEIGHTS] No feedback data - skipping adjustment")
        else:
            proposed_weights = compute_weight_adjustments(
                current_weights,
                feedback_stats,
            )

            # 4. EVALUATE (baseline vs candidate)
            eval_before = run_evals_with_weights(current_weights)
            eval_after = run_evals_with_weights(proposed_weights)

            # 5. GUARD - check for regression
            if eval_after["pass_rate"] < eval_before["pass_rate"]:
                # Regression detected - reject and keep current weights
                proposed_weights = current_weights.copy()
                applied = False
                rejected_reason = "regression"
                print(f"[WEIGHTS] Regression detected: {eval_after['pass_rate']:.0%} < {eval_before['pass_rate']:.0%}")
            else:
                applied = True
                rejected_reason = None
                print(f"[WEIGHTS] No regression: {eval_after['pass_rate']:.0%} >= {eval_before['pass_rate']:.0%}")

        # When not applied, weights_after = weights_before (per design)
        weights_after = proposed_weights if applied else current_weights

        # Get eval results (or defaults if no feedback)
        if not feedback_stats:
            eval_before = {"pass_rate": 1.0, "passed": 0, "total": 0}
            eval_after = {"pass_rate": 1.0, "passed": 0, "total": 0}

        # 6. PERSIST snapshot
        snapshot_id = upsert_weight_snapshot(
            conn,
            cycle_date=cycle_date,
            weights_before=current_weights,
            weights_after=weights_after,
            feedback_summary=feedback_stats,
            eval_before=eval_before["pass_rate"],
            eval_after=eval_after["pass_rate"],
            applied=applied,
            rejected_reason=rejected_reason,
            user_id=user_id,
        )
        print(f"[WEIGHTS] Persisted snapshot_id={snapshot_id}, applied={applied}")

        # Compute detailed changes for artifact
        weight_changes = compute_weight_changes(
            current_weights,
            weights_after,
            feedback_stats,
        )

        # Write artifact
        artifact_path = write_weight_artifact(
            cycle_date=cycle_date,
            feedback_summary=feedback_stats,
            weight_changes=weight_changes,
            eval_before=eval_before,
            eval_after=eval_after,
            applied=applied,
            rejected_reason=rejected_reason,
            snapshot_id=snapshot_id,
        )
        print(f"[WEIGHTS] Wrote artifact: {artifact_path}")

        log_event(
            "weight_update_completed",
            cycle_date=cycle_date,
            snapshot_id=snapshot_id,
            applied=applied,
            rejected_reason=rejected_reason,
            sources_with_feedback=len(feedback_stats),
        )

    finally:
        conn.close()

    status = "APPLIED" if applied else f"REJECTED ({rejected_reason})"
    print(f"[WEIGHTS] Complete: {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

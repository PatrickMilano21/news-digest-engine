from __future__ import annotations

from datetime import datetime, timezone

import os

from evals.cases import EvalCase, load_cases
from src.rss_parse import parse_rss
from src.scoring import rank_items
from src.explain import explain_item

from evals.taxonomy import (
    EVAL_FIXTURE_READ_FAIL,
    EVAL_RSS_PARSE_FAIL,
    EVAL_MISMATCH_KEYWORD,
    EVAL_MISMATCH_TOPIC,
    EVAL_MISMATCH_RECENCY,
    EVAL_MISMATCH_SOURCE_WEIGHT,
    EVAL_MISMATCH_TIEBREAK_OR_EXPECTATION,
)


def run_eval_case(case, *, now) -> dict:
    
    try:
        xml = open(case.fixture_path, "r", encoding="utf-8").read()
    except Exception:
        return {
            "case_id": case.case_id,
            "expected_titles": list(case.expected_titles),
            "actual_titles": [],
            "pass": False,
            "error_code": EVAL_FIXTURE_READ_FAIL,
            "mismatch": None,
        }

    try:
        items = parse_rss(xml, source=case.source)
    except Exception:
        return {
            "case_id": case.case_id,
            "expected_titles": list(case.expected_titles),
            "actual_titles": [],
            "pass": False,
            "error_code": EVAL_RSS_PARSE_FAIL,
            "mismatch": None,
        }
    ranked = rank_items(items, now=now, top_n=case.top_n, cfg=case.cfg)

    actual_titles = [it.title for it in ranked]
    expected_titles = list(case.expected_titles)

    passed = actual_titles == expected_titles
    mismatch = None
    
    if not passed:
        mismatch_index = None
        for i in range(min(len(actual_titles), len(expected_titles))):
            if actual_titles[i] != expected_titles[i]:
                mismatch_index = i
                break
        if mismatch_index is None:
            mismatch_index = 0

        expected_title = expected_titles[mismatch_index] if mismatch_index < len(expected_titles) else None
        actual_title = actual_titles[mismatch_index] if mismatch_index < len(actual_titles) else None

        expected_item = next((it for it in items if it.title == expected_title), None) if expected_title else None
        actual_item = next((it for it in ranked if it.title == actual_title), None) if actual_title else None

        mismatch = {
            "index": mismatch_index,
            "expected_title": expected_title,
            "actual_title": actual_title,
            "expected_explain": explain_item(expected_item, now=now, cfg=case.cfg) if expected_item else None,
            "actual_explain": explain_item(actual_item, now=now, cfg=case.cfg) if actual_item else None,
        }

    error_code = None
    if not passed:
        # mismatch is either None or a dict with expected_explain / actual_explain
        mm = mismatch or {}
        e = mm.get("expected_explain") or {}
        a = mm.get("actual_explain") or {}

        if e.get("matched_keywords") != a.get("matched_keywords"):
            error_code = EVAL_MISMATCH_KEYWORD
        elif e.get("matched_topics") != a.get("matched_topics"):
            error_code = EVAL_MISMATCH_TOPIC
        elif e.get("recency_decay") != a.get("recency_decay"):
            error_code = EVAL_MISMATCH_RECENCY
        elif e.get("source_weight") != a.get("source_weight"):
            error_code = EVAL_MISMATCH_SOURCE_WEIGHT
        else:
            error_code = EVAL_MISMATCH_TIEBREAK_OR_EXPECTATION

    return{
        "case_id": case.case_id,
        "expected_titles": expected_titles,
        "actual_titles": actual_titles,
        "pass": passed,
        "mismatch": mismatch,
        "error_code": error_code
    }


def run_all(*, now) -> dict:
    cases = load_cases()
    result = [run_eval_case(c, now=now) for c in cases]
    total = len(result)
    passed = sum(1 for r in result if r["pass"])
    failed = total - passed

    return{
        "total":total,
        "passed":passed,
        "failed":failed,
        "results":result,
    }

def format_report(out: dict) -> str:
    lines: list[str] = []
    total = out["total"]
    passed = out["passed"]
    failed = out["failed"]

    lines.append(f"EVAL SUMMARY: total={total} passed={passed} failed={failed}")
    if failed == 0:
        lines.append("ALL PASS")
        return "\n".join(lines)
    
    for r in out["results"]:
        if r["pass"]:
            continue
        lines.append("")
        lines.append(f"FAIL: {r['case_id']}")
        lines.append(f"EXPECTED: {r['expected_titles']}")
        lines.append(f"ACTUAL:   {r['actual_titles']}")
        mm = r.get("mismatch")
        if mm:
            lines.append(f"MISMATCH_AT: {mm['index']}")
            lines.append(f"EXPECTED_TITLE: {mm['expected_title']}")
            lines.append(f"ACTUAL_TITLE:   {mm['actual_title']}")
            lines.append(f"EXPECTED_EXPLAIN: {mm['expected_explain']}")
            lines.append(f"ACTUAL_EXPLAIN:   {mm['actual_explain']}")

    return "\n".join(lines)

def write_eval_report(out: dict, *, day: str) -> str:
    os.makedirs("artifacts", exist_ok=True)
    path = os.path.join("artifacts", f"eval_report_{day}.md")

    total = out["total"]
    passed = out["passed"]
    failed = out["failed"]
    pass_rate = (passed / total) if total else 0.0

    # Breakdown by error_code
    breakdown: dict[str, int] = {}
    for r in out["results"]:
        if r["pass"]:
            continue
        code = r.get("error_code") or "UNKNOWN"
        breakdown[code] = breakdown.get(code, 0) + 1

    lines: list[str] = []
    lines.append(f"# Eval Report — {day}")
    lines.append("")
    lines.append(f"- total: {total}")
    lines.append(f"- passed: {passed}")
    lines.append(f"- failed: {failed}")
    lines.append(f"- pass_rate: {pass_rate:.2%}")
    lines.append("")

    lines.append("## Failure breakdown")
    if not breakdown:
        lines.append("- (none)")
    else:
        for code, count in sorted(breakdown.items()):
            lines.append(f"- {code}: {count}")
    lines.append("")

    lines.append("## Failures (diffs)")
    any_fail = False
    for r in out["results"]:
        if r["pass"]:
            continue
        any_fail = True
        lines.append(f"### {r['case_id']}")
        lines.append(f"- error_code: {r.get('error_code')}")
        lines.append(f"- expected: {r.get('expected_titles')}")
        lines.append(f"- actual: {r.get('actual_titles')}")
        mm = r.get("mismatch")
        if mm:
            lines.append(f"- mismatch_index: {mm.get('index')}")
            lines.append(f"- expected_title: {mm.get('expected_title')}")
            lines.append(f"- actual_title: {mm.get('actual_title')}")
        lines.append("")
    if not any_fail:
        lines.append("- (none)")
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return path



if __name__ == "__main__":
    now = datetime(2026, 1, 14, 23, 59, 59, tzinfo=timezone.utc)
    out = run_all(now=now)
    print(format_report(out))

    day = now.date().isoformat()
    report_path = write_eval_report(out, day=day)
    print(f"WROTE {report_path}")

    raise SystemExit(0 if out["failed"] == 0 else 1)



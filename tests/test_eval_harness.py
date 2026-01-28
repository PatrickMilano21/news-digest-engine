from __future__ import annotations

from datetime import datetime, timezone

from evals.cases import load_cases
from evals.runner import run_all


def test_load_cases_two_cases():
    cases = load_cases()
    assert len(cases) == 50
    for c in cases:
        assert c.case_id
        assert c.fixture_path
        assert c.source
        assert isinstance(c.expected_titles, list)
        assert c.top_n >= 1


def test_eval_cases_pass_with_fixed_now():
    now = datetime(2026, 1, 14, 23, 59, 59, tzinfo=timezone.utc)
    out = run_all(now=now)
    assert out["total"] == 50
    if out["failed"] != 0:
        failing = [r for r in out["results"] if not r["pass"]]
        first = failing[0]
        raise AssertionError(
            f"failed={out['failed']} first_case={first['case_id']} "
            f"expected={first['expected_titles']} actual={first['actual_titles']}"
        )
    assert out["passed"] == 50


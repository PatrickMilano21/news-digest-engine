"""Tests for summary quality eval harness."""
from __future__ import annotations

from src.llm_schemas.summary import SummaryResult, Citation
from evals.summary_cases import load_summary_cases
from evals.summary_runner import run_all_cases, summarize_results
from evals.summary_checks import check_summary_length
from evals.summary_taxonomy import SUMMARY_TOO_SHORT


def test_load_summary_cases_returns_32():
    """Verify we have exactly 32 test cases."""
    cases = load_summary_cases()
    assert len(cases) == 32
    for c in cases:
        assert c.case_id
        assert c.result is not None
        assert isinstance(c.expected_failures, tuple)


# -----------------------------------------------------------------------------
# check_summary_length tests
# -----------------------------------------------------------------------------

def test_check_summary_length_passes_for_long_summary():
    """Summary >= 10 chars should pass."""
    result = SummaryResult(
        summary="This is long enough.",
        tags=["test"],
        citations=[Citation(source_url="https://example.com", evidence_snippet="test")],
        confidence=0.9,
    )
    assert check_summary_length(result) is None


def test_check_summary_length_fails_for_short_summary():
    """Summary < 10 chars should fail."""
    result = SummaryResult(
        summary="Short",  # 5 chars
        tags=["test"],
        citations=[Citation(source_url="https://example.com", evidence_snippet="Short")],
        confidence=0.9,
    )
    assert check_summary_length(result) == SUMMARY_TOO_SHORT


def test_check_summary_length_skips_refusals():
    """Refusals don't need a summary."""
    result = SummaryResult(refusal="NO_EVIDENCE")
    assert check_summary_length(result) is None


def test_summary_eval_cases_all_pass():
    """All summary check test cases should pass."""
    results = run_all_cases()
    summary = summarize_results(results)

    if summary["failed"] != 0:
        first_fail = summary["failures"][0]
        raise AssertionError(
            f"failed={summary['failed']} first_case={first_fail['name']} "
            f"expected={first_fail['expected']} actual={first_fail['actual']}"
        )

    assert summary["passed"] == summary["total"]
    assert summary["pass_rate"] == 100.0


def test_summarize_results_calculates_totals():
    """Verify summarize_results math is correct."""
    results = run_all_cases()
    summary = summarize_results(results)

    assert summary["total"] == len(results)
    assert summary["passed"] + summary["failed"] == summary["total"]
    assert 0 <= summary["pass_rate"] <= 100

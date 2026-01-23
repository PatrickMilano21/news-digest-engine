"""Eval runner for summary quality checks."""
from __future__ import annotations

from dataclasses import dataclass

from evals.summary_checks import run_all_checks
from evals.summary_cases import SummaryCheckCase, load_summary_cases


@dataclass
class CaseResult:
    """Result of running checks on a single test case."""
    name: str
    passed: bool
    expected: list[str]
    actual: list[str]

def run_case(case: SummaryCheckCase) -> CaseResult:
    """Run all checks on a single test case."""
    actual_failures = run_all_checks(
        result=case.result,
        evidence=case.evidence,
        item_url=case.item_url,
    )
    
    #Compare as sets (order doesn't matter)
    passed = set(actual_failures) == set(case.expected_failures)

    return CaseResult(
        name=case.case_id,
        passed=passed,
        expected=list(case.expected_failures),
        actual=actual_failures,
    )

def run_all_cases(cases: list[SummaryCheckCase] | None = None) -> list[CaseResult]:
    """Run all test cases and return results."""
    if cases is None:
        cases = load_summary_cases()

    return [run_case(case) for case in cases]

def summarize_results(results: list[CaseResult]) -> dict:
    """Generate summary statistics from results."""
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed 

    #Group failures by what went wrong
    failure_details = []
    for r in results:
        if not r.passed:
            failure_details.append({
                "name": r.name,
                "expected": r.expected,
                "actual": r.actual,
            })
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / total * 100, 1) if total > 0 else 0,
        "failures": failure_details,
    }
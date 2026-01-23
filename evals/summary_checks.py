"""
Summary quality check functions.

Each check function:
- Returns a failure code (str) if the check fails
- Returns None if the check passes
- NEVER modifies the input SummaryResult

INVARIANT: All functions are pure - no side effects, no mutations.
"""
from __future__ import annotations

from pydantic import ValidationError

from src.llm_schemas.summary import SummaryResult
from evals.summary_taxonomy import (
    SCHEMA_INVALID,
    MISSING_CITATIONS,
    SNIPPET_NOT_GROUNDED,
    URL_MISMATCH,
    INVALID_REFUSAL_CODE,
    NO_TAGS,
    TOO_MANY_TAGS,
    SUMMARY_TOO_SHORT,
    VALID_REFUSAL_CODES,
    MAX_TAGS,
    MIN_TAGS,
    MIN_SUMMARY_LENGTH,
)


def check_schema_valid(data: dict) -> str | None:
    """
    Check if data can be parsed as valid SummaryResult
    Args: 
        data: raw dict (before pydantic parsing)
    returns: 
        SCHEMA_INVALID if parsing fails, None if valid
    """
    try:
        SummaryResult(**data)
        return None
    except (ValidationError, TypeError):
        return SCHEMA_INVALID

def check_has_citations(result: SummaryResult) -> str | None:
    """
    if summary is present, citations must be non-empty.
    Refusals are allowed to have no citations.
    """
    #Refusals dont need citations
    if result.refusal:
        return None
    #Summary present but no citations
    if result.summary and len(result.citations) ==0:
        return MISSING_CITATIONS
    return None

def check_citations_grounded(result: SummaryResult, evidence: str) -> str | None:
    """
    Every citation.evidence_snippet must be exact substring of evidence
    Args:
        result: the SummaryResult to check
        evidence: the source text citaiotns should reference
    """
    # Skip if refusal (no citations to check)
    if result.refusal:
        return None
    #Check each citation
    for citation in result.citations:
        if citation.evidence_snippet not in evidence:
            return SNIPPET_NOT_GROUNDED
    
    return None

def check_citation_urls(result: SummaryResult, item_url: str) -> str | None:
    """
    Every citation.source_url must match the item's URL.
    Args:
        result: The SummaryResult to check
        item_url: The expected URL for all citations
    """
    # Skip if refusal
    if result.refusal:
        return None
    #Check each citation URL
    for citation in result.citations:
        if citation.source_url != item_url:
            return URL_MISMATCH
    
    return None

def check_refusal_code_valid(result: SummaryResult) -> str | None:
    """
    If refusal is present, it must be a known refusal code.
    """
    # No refusal = nothing to check
    if not result.refusal:
        return None

    # Check if refusal is in allowed set
    if result.refusal not in VALID_REFUSAL_CODES:
        return INVALID_REFUSAL_CODE

    return None


def check_tag_count(result: SummaryResult) -> str | None:
    """
    If summary is present, tags must be within bounds.
    
    Rules:
    - At least MIN_TAGS (1) tag
    - At most MAX_TAGS (5) tags
    """
    # Skip if refusal (tags not required)
    if result.refusal:
        return None

    tag_count = len(result.tags)

    if tag_count < MIN_TAGS:
        return NO_TAGS

    if tag_count > MAX_TAGS:
        return TOO_MANY_TAGS

    return None

def check_summary_length(result: SummaryResult) -> str | None:
    """
    Summary must be at least MIN_SUMMARY_LENGTH characters.
    REfusals are allowed to have no summary.
    """
    # Skip if refusal (no summarye expected)
    if result.refusal:
        return None
    #Check Length
    if result.summary and len(result.summary) < MIN_SUMMARY_LENGTH:
        return SUMMARY_TOO_SHORT
    return None


def run_all_checks(result: SummaryResult, evidence: str, item_url: str) -> list[str]:
    """
    Run all summary quality checks

    Args:
        result: The SummaryResult to evaluate
        evidence: Source text for groundign checks
        item_url: expected URL for citation URL checks
    Returns:
        List of failure codes. Empty list = all checks passed
    Contract:
        Never modifies result
        Always returns a list (may be empty)
        deterministic: same inputs -> same outputs
    """
    failures: list[str] = []
    #run each check, collect failures
    checks = [
        check_has_citations(result),
        check_citations_grounded(result, evidence),
        check_citation_urls(result, item_url),
        check_refusal_code_valid(result),
        check_tag_count(result),
        check_summary_length(result),
    ]

    for code in checks:
        if code is not None:
            failures.append(code)
    return failures
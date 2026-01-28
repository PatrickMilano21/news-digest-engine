"""Grounding validation for LLM outputs.

Enforces that all citations are exact substrings of provided evidence.
This is the core trust boundary - if a citation can't be verified,
the entire result is rejected.
"""
from __future__ import annotations

from src.llm_schemas.summary import SummaryResult
from src.error_codes import NO_EVIDENCE, GROUNDING_FAIL


def validate_grounding(result: SummaryResult, evidence: str | None) -> SummaryResult:
    """
    Validate that a SummaryResult is grounded in provided evidence.
    
    Rules (applied in order):
    1. If result already has refusal, pass through unchanged
    2. If evidence is empty/None, refuse with NO_EVIDENCE
    3. If any citation snippet is not exact substring of evidence, refuse with GROUNDING_FAIL
    
    Args:
        result: SummaryResult from LLM adapter
        evidence: The source text that citations must reference
        
    Returns:
        Original result if valid, or new SummaryResult with refusal
        
    Contract:
        - Never raises exceptions
        - Always returns valid SummaryResult
    """
    # Rule 1: Pass through existing refusals
    if result.refusal:
        return result
    
    # Rule 2: Evidence must exist
    if not evidence or not evidence.strip():
        return SummaryResult(refusal=NO_EVIDENCE)
    
    # Rule 3: Every citation must be exact substring
    for citation in result.citations:
        if citation.evidence_snippet not in evidence:
            return SummaryResult(refusal=GROUNDING_FAIL)
    
    # All check passed
    return result
"""Tests for grounding validation.

These tests verify that validate_grounding() correctly enforces
the trust boundary: citations must be exact substrings of evidence.
"""

from src.grounding import validate_grounding
from src.llm_schemas.summary import SummaryResult, Citation
from src.error_codes import NO_EVIDENCE, GROUNDING_FAIL, LLM_DISABLED

# ---------------------------------------------------------------------
# Test 1: Pass-through existing refusals
# ---------------------------------------------------------------------
def test_passthrough_existing_refusal():
    """If result already has refusal, return in unchanged."""
    result = SummaryResult(refusal=LLM_DISABLED)
    evidence = "Some evidence text"

    validated = validate_grounding(result, evidence)

    assert validated.refusal == LLM_DISABLED
    assert validated is result

# ---------------------------------------------------------------------
# Test 2-4: Evidence must exist
# ---------------------------------------------------------------------
def test_refuse_when_evidence_empty():
    """Empty evidence string returns NO_EVIDENCE refusal"""
    result = SummaryResult(
        summary="Test summary",
        citations=[Citation(source_url="http://x.com", evidence_snippet="test")]
    )
    evidence = ""

    validated = validate_grounding(result, evidence)

    assert validated.refusal == NO_EVIDENCE
    assert validated.summary is None

def test_refuse_when_evidence_whitespace():
    """Whitespace-only evidence returns NO_EVIDENCE refusal."""
    result = SummaryResult(
        summary="Test summary",
        citations=[Citation(source_url="http://x.com", evidence_snippet="test")]
    )
    evidence = "   \n\t  "

    validated = validate_grounding(result, evidence)

    assert validated.refusal == NO_EVIDENCE


def test_refuse_when_evidence_none():
    """None evidence returns NO_EVIDENCE refusal."""
    result = SummaryResult(
        summary="Test summary",
        citations=[Citation(source_url="http://x.com", evidence_snippet="test")]
    )
    evidence = None

    validated = validate_grounding(result, evidence)

    assert validated.refusal == NO_EVIDENCE

# ---------------------------------------------------------------------
# Test 5: Citation not in evidence
# ---------------------------------------------------------------------
def test_refuse_when_snippet_not_substring():
    """Citation snippet not found in evidence returns GROUNDING_FAIL."""
    result = SummaryResult(
        summary="Test summary",
        citations=[Citation(
            source_url="http://x.com",
            evidence_snippet="This text does not exist"
        )]
    )
    evidence = "Apple announced the new iPhone today."

    validated = validate_grounding(result, evidence)

    assert validated.refusal == GROUNDING_FAIL
    assert validated.summary is None

# ---------------------------------------------------------------------
# Test 6: Valid citation (exact substring)
# ---------------------------------------------------------------------
def test_accept_when_snippet_exact_match():
    """Citation that is exact substring of evidence passes."""
    result = SummaryResult(
        summary="Apple released new iPhone.",
        citations=[Citation(
            source_url="http://x.com",
            evidence_snippet="new iPhone today"
        )]
    )
    evidence = "Apple announced the new iPhone today."
    
    validated = validate_grounding(result, evidence)
    
    assert validated.refusal is None
    assert validated.summary == "Apple released new iPhone."
    assert validated is result  # Same object returned


# ---------------------------------------------------------------------
# Test 7: Multiple valid citations
# ---------------------------------------------------------------------
def test_accept_multiple_valid_citations():
    """All citations valid means summary passes."""
    result = SummaryResult(
        summary="Apple announced iPhone with USB-C.",
        citations=[
            Citation(source_url="http://x.com", evidence_snippet="Apple announced"),
            Citation(source_url="http://x.com", evidence_snippet="USB-C connectivity")
        ]
    )
    evidence = "Apple announced the new iPhone with USB-C connectivity today."
    
    validated = validate_grounding(result, evidence)

    assert validated.refusal is None
    assert validated.summary == "Apple announced iPhone with USB-C."


# ---------------------------------------------------------------------
# Test 8: One invalid citation fails entire result
# ---------------------------------------------------------------------
def test_refuse_when_one_citation_invalid():
    """If any citation is invalid, entire result is refused."""
    result = SummaryResult(
        summary="Apple announced iPhone with USB-C.",
        citations=[
            Citation(source_url="http://x.com", evidence_snippet="Apple announced"),  # Valid
            Citation(source_url="http://x.com", evidence_snippet="5G support")  # Invalid!
        ]
    )
    evidence = "Apple announced the new iPhone with USB-C connectivity today."

    validated = validate_grounding(result, evidence)
    
    assert validated.refusal == GROUNDING_FAIL
    assert validated.summary is None
"""
Summary evaluation test cases.

Each case defines:
- A SummaryResult to check
- The evidence it should be grounded in
- The item URL citations should reference
- Expected failure codes (empty = should pass)

Cases are deterministic and cover all check functions.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.llm_schemas.summary import SummaryResult, Citation
from evals.summary_taxonomy import (
    SNIPPET_NOT_GROUNDED,
    URL_MISMATCH,
    INVALID_REFUSAL_CODE,
    NO_TAGS,
    TOO_MANY_TAGS,
    SUMMARY_TOO_SHORT,
)


@dataclass(frozen=True)
class SummaryCheckCase:
    """A single eval test case."""
    case_id: str
    result: SummaryResult
    evidence: str
    item_url: str
    expected_failures: tuple[str, ...]  # Use tuple for immutability


def load_summary_cases() -> list[SummaryCheckCase]:
    """Load all summary check test cases."""
    cases: list[SummaryCheckCase] = []
    
    # -------------------------------------------------------------------------
    # VALID SUMMARIES (should pass all checks)
    # -------------------------------------------------------------------------
    
    # Case 1: Simple valid summary
    cases.append(SummaryCheckCase(
        case_id="valid_simple",
        result=SummaryResult(
            summary="The company reported strong earnings.",
            tags=["business"],
            citations=[Citation(
                source_url="https://example.com/article",
                evidence_snippet="reported strong earnings"
            )],
            confidence=0.9,
        ),
        evidence="The company reported strong earnings this quarter.",
        item_url="https://example.com/article",
        expected_failures=(),
    ))
    
    # Case 2: Valid with multiple citations
    cases.append(SummaryCheckCase(
        case_id="valid_multiple_citations",
        result=SummaryResult(
            summary="Revenue grew and profits increased.",
            tags=["business", "finance"],
            citations=[
                Citation(
                    source_url="https://example.com/news",
                    evidence_snippet="Revenue grew 20%"
                ),
                Citation(
                    source_url="https://example.com/news",
                    evidence_snippet="profits increased significantly"
                ),
            ],
            confidence=0.85,
        ),
        evidence="Revenue grew 20% year over year. Meanwhile, profits increased significantly.",
        item_url="https://example.com/news",
        expected_failures=(),
    ))
    
    # Case 3: Valid with max tags (5)
    cases.append(SummaryCheckCase(
        case_id="valid_max_tags",
        result=SummaryResult(
            summary="Tech company launches new product.",
            tags=["tech", "product", "launch", "innovation", "news"],
            citations=[Citation(
                source_url="https://tech.com/article",
                evidence_snippet="launches new product"
            )],
            confidence=0.8,
        ),
        evidence="Tech company launches new product today.",
        item_url="https://tech.com/article",
        expected_failures=(),
    ))

    # Case 4: Valid with minimum tags (1)
    cases.append(SummaryCheckCase(
        case_id="valid_min_tags",
        result=SummaryResult(
            summary="Market update.",
            tags=["finance"],
            citations=[Citation(
                source_url="https://finance.com/update",
                evidence_snippet="Market update"
            )],
            confidence=0.7,
        ),
        evidence="Market update for today.",
        item_url="https://finance.com/update",
        expected_failures=(),
    ))

    # Case 5: Valid with long summary
    cases.append(SummaryCheckCase(
        case_id="valid_long_summary",
        result=SummaryResult(
            summary="The quarterly earnings report showed significant growth across all divisions, with particularly strong performance in the cloud services sector.",
            tags=["business", "earnings", "cloud"],
            citations=[Citation(
                source_url="https://example.com/earnings",
                evidence_snippet="significant growth across all divisions"
            )],
            confidence=0.9,
        ),
        evidence="The quarterly earnings report showed significant growth across all divisions.",
        item_url="https://example.com/earnings",
        expected_failures=(),
    ))
    
    # -------------------------------------------------------------------------
    # VALID REFUSALS (should pass all checks)
    # -------------------------------------------------------------------------
    
    # Case 6: Valid refusal - NO_EVIDENCE
    cases.append(SummaryCheckCase(
        case_id="valid_refusal_no_evidence",
        result=SummaryResult(refusal="NO_EVIDENCE"),
        evidence="",
        item_url="https://example.com/article",
        expected_failures=(),
    ))
    
    # Case 7: Valid refusal - LLM_PARSE_FAIL
    cases.append(SummaryCheckCase(
        case_id="valid_refusal_parse_fail",
        result=SummaryResult(refusal="LLM_PARSE_FAIL"),
        evidence="Some evidence here.",
        item_url="https://example.com/article",
        expected_failures=(),
    ))
    
    # Case 8: Valid refusal - GROUNDING_FAIL
    cases.append(SummaryCheckCase(
        case_id="valid_refusal_grounding_fail",
        result=SummaryResult(refusal="GROUNDING_FAIL"),
        evidence="Some evidence.",
        item_url="https://example.com/article",
        expected_failures=(),
    ))
    
    # Case 9: Valid refusal - PIPELINE_ERROR
    cases.append(SummaryCheckCase(
        case_id="valid_refusal_pipeline_error",
        result=SummaryResult(refusal="PIPELINE_ERROR"),
        evidence="Evidence text.",
        item_url="https://example.com/article",
        expected_failures=(),
    ))
    
    # -------------------------------------------------------------------------
    # MISSING CITATIONS (should fail)
    # -------------------------------------------------------------------------

    # Case 10: Summary with empty citations list
    # NOTE: This would actually fail Pydantic validation first,
    # but we test it defensively
    # We need to create this carefully since Pydantic enforces citations
    # For eval purposes, we'll assume we receive already-parsed data
    # that somehow bypassed validation

    # Case 11-13: We'll handle these differently since Pydantic enforces citations
    # For now, let's focus on cases that CAN exist
    
    # -------------------------------------------------------------------------
    # BAD GROUNDING (snippet not in evidence)
    # -------------------------------------------------------------------------
    
    # Case 10: Citation snippet not in evidence
    cases.append(SummaryCheckCase(
        case_id="bad_grounding_snippet_missing",
        result=SummaryResult(
            summary="Company had record profits.",
            tags=["business"],
            citations=[Citation(
                source_url="https://example.com/article",
                evidence_snippet="record profits of one billion dollars"  # Not in evidence!
            )],
            confidence=0.9,
        ),
        evidence="The company reported strong earnings this quarter.",
        item_url="https://example.com/article",
        expected_failures=(SNIPPET_NOT_GROUNDED,),
    ))
    
    # Case 11: Partial match (not exact substring)
    cases.append(SummaryCheckCase(
        case_id="bad_grounding_partial_match",
        result=SummaryResult(
            summary="Profits rose.",
            tags=["finance"],
            citations=[Citation(
                source_url="https://example.com/article",
                evidence_snippet="Profits rose dramatically"  # Evidence has just "Profits rose"
            )],
            confidence=0.8,
        ),
        evidence="Profits rose this quarter.",
        item_url="https://example.com/article",
        expected_failures=(SNIPPET_NOT_GROUNDED,),
    ))
    
    # Case 12: Case sensitivity (exact match required)
    cases.append(SummaryCheckCase(
        case_id="bad_grounding_case_mismatch",
        result=SummaryResult(
            summary="Revenue increased.",
            tags=["business"],
            citations=[Citation(
                source_url="https://example.com/article",
                evidence_snippet="REVENUE INCREASED"  # Evidence is lowercase
            )],
            confidence=0.7,
        ),
        evidence="The company said revenue increased.",
        item_url="https://example.com/article",
        expected_failures=(SNIPPET_NOT_GROUNDED,),
    ))

    # Case 13: One of multiple citations is bad
    cases.append(SummaryCheckCase(
        case_id="bad_grounding_one_of_many",
        result=SummaryResult(
            summary="Good news overall.",
            tags=["news"],
            citations=[
                Citation(
                    source_url="https://example.com/article",
                    evidence_snippet="Good news"  # This IS in evidence
                ),
                Citation(
                    source_url="https://example.com/article",
                    evidence_snippet="fantastic results"  # This is NOT
                ),
            ],
            confidence=0.8,
        ),
        evidence="Good news from the company today.",
        item_url="https://example.com/article",
        expected_failures=(SNIPPET_NOT_GROUNDED,),
    ))

    # -------------------------------------------------------------------------
    # URL MISMATCH
    # -------------------------------------------------------------------------
    
    # Case 14: Citation URL doesn't match item URL
    cases.append(SummaryCheckCase(
        case_id="url_mismatch_different_domain",
        result=SummaryResult(
            summary="News reported.",
            tags=["news"],
            citations=[Citation(
                source_url="https://other-site.com/article",  # Wrong!
                evidence_snippet="News reported"
            )],
            confidence=0.8,
        ),
        evidence="News reported today.",
        item_url="https://example.com/article",
        expected_failures=(URL_MISMATCH,),
    ))

    # Case 15: URL path mismatch
    cases.append(SummaryCheckCase(
        case_id="url_mismatch_different_path",
        result=SummaryResult(
            summary="Update shared.",
            tags=["update"],
            citations=[Citation(
                source_url="https://example.com/wrong-path",  # Wrong path
                evidence_snippet="Update shared"
            )],
            confidence=0.7,
        ),
        evidence="Update shared with users.",
        item_url="https://example.com/correct-path",
        expected_failures=(URL_MISMATCH,),
    ))

    # Case 16: One citation URL wrong, one correct
    cases.append(SummaryCheckCase(
        case_id="url_mismatch_one_of_many",
        result=SummaryResult(
            summary="Two facts.",
            tags=["facts"],
            citations=[
                Citation(
                    source_url="https://example.com/article",  # Correct
                    evidence_snippet="First fact"
                ),
                Citation(
                    source_url="https://wrong.com/article",  # Wrong
                    evidence_snippet="Second fact"
                ),
            ],
            confidence=0.8,
        ),
        evidence="First fact. Second fact.",
        item_url="https://example.com/article",
        expected_failures=(URL_MISMATCH,),
    ))

    # -------------------------------------------------------------------------
    # INVALID REFUSAL CODE
    # -------------------------------------------------------------------------

    # Case 17: Unknown refusal code
    cases.append(SummaryCheckCase(
        case_id="invalid_refusal_unknown",
        result=SummaryResult(refusal="UNKNOWN_ERROR"),
        evidence="Some evidence.",
        item_url="https://example.com/article",
        expected_failures=(INVALID_REFUSAL_CODE,),
    ))
    
    # Case 18: Typo in refusal code
    cases.append(SummaryCheckCase(
        case_id="invalid_refusal_typo",
        result=SummaryResult(refusal="NO_EVIDNECE"),  # Typo!
        evidence="Evidence here.",
        item_url="https://example.com/article",
        expected_failures=(INVALID_REFUSAL_CODE,),
    ))

    # Case 19: Random string as refusal
    cases.append(SummaryCheckCase(
        case_id="invalid_refusal_random",
        result=SummaryResult(refusal="I cannot summarize this"),
        evidence="Evidence.",
        item_url="https://example.com/article",
        expected_failures=(INVALID_REFUSAL_CODE,),
    ))

    # -------------------------------------------------------------------------
    # TAG ISSUES
    # -------------------------------------------------------------------------

    # Case 20: No tags (empty list)
    cases.append(SummaryCheckCase(
        case_id="no_tags_empty",
        result=SummaryResult(
            summary="A summary.",
            tags=[],  # Empty!
            citations=[Citation(
                source_url="https://example.com/article",
                evidence_snippet="A summary"
            )],
            confidence=0.8,
        ),
        evidence="A summary of the news.",
        item_url="https://example.com/article",
        expected_failures=(NO_TAGS,),
    ))

    # Case 21: Too many tags (6)
    cases.append(SummaryCheckCase(
        case_id="too_many_tags_six",
        result=SummaryResult(
            summary="Lots of topics.",
            tags=["one", "two", "three", "four", "five", "six"],  # 6 > 5
            citations=[Citation(
                source_url="https://example.com/article",
                evidence_snippet="Lots of topics"
            )],
            confidence=0.8,
        ),
        evidence="Lots of topics covered here.",
        item_url="https://example.com/article",
        expected_failures=(TOO_MANY_TAGS,),
    ))

    # Case 22: Way too many tags (10)
    cases.append(SummaryCheckCase(
        case_id="too_many_tags_ten",
        result=SummaryResult(
            summary="Everything tagged.",
            tags=["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"],  # 10!
            citations=[Citation(
                source_url="https://example.com/article",
                evidence_snippet="Everything tagged"
            )],
            confidence=0.5,
        ),
        evidence="Everything tagged in this article.",
        item_url="https://example.com/article",
        expected_failures=(TOO_MANY_TAGS,),
    ))
    
    # -------------------------------------------------------------------------
    # MULTIPLE FAILURES
    # -------------------------------------------------------------------------

    # Case 23: Bad grounding AND wrong URL
    cases.append(SummaryCheckCase(
        case_id="multiple_grounding_and_url",
        result=SummaryResult(
            summary="Double trouble.",
            tags=["test"],
            citations=[Citation(
                source_url="https://wrong.com/article",  # Wrong URL
                evidence_snippet="not in evidence"  # Not grounded
            )],
            confidence=0.5,
        ),
        evidence="Actual evidence text here.",
        item_url="https://example.com/article",
        expected_failures=(SNIPPET_NOT_GROUNDED, URL_MISMATCH),
    ))

    # Case 24: Bad grounding AND too many tags
    cases.append(SummaryCheckCase(
        case_id="multiple_grounding_and_tags",
        result=SummaryResult(
            summary="Multiple problems detected.",
            tags=["one", "two", "three", "four", "five", "six"],  # Too many
            citations=[Citation(
                source_url="https://example.com/article",
                evidence_snippet="fabricated quote"  # Not in evidence
            )],
            confidence=0.3,
        ),
        evidence="Real evidence here.",
        item_url="https://example.com/article",
        expected_failures=(SNIPPET_NOT_GROUNDED, TOO_MANY_TAGS),
    ))

    # Case 25: Wrong URL AND no tags
    cases.append(SummaryCheckCase(
        case_id="multiple_url_and_notags",
        result=SummaryResult(
            summary="More issues.",
            tags=[],  # No tags
            citations=[Citation(
                source_url="https://wrong.com/path",  # Wrong URL
                evidence_snippet="More issues"
            )],
            confidence=0.4,
        ),
        evidence="More issues to report.",
        item_url="https://example.com/article",
        expected_failures=(URL_MISMATCH, NO_TAGS),
    ))

    # -------------------------------------------------------------------------
    # EDGE CASES
    # -------------------------------------------------------------------------

    # Case 26: Snippet at very start of evidence
    cases.append(SummaryCheckCase(
        case_id="edge_snippet_at_start",
        result=SummaryResult(
            summary="Breaking news.",
            tags=["news"],
            citations=[Citation(
                source_url="https://example.com/article",
                evidence_snippet="Breaking"  # First word
            )],
            confidence=0.9,
        ),
        evidence="Breaking news from the company.",
        item_url="https://example.com/article",
        expected_failures=(),  # Should pass
    ))

    # Case 27: Snippet at very end of evidence
    cases.append(SummaryCheckCase(
        case_id="edge_snippet_at_end",
        result=SummaryResult(
            summary="Company news.",
            tags=["business"],
            citations=[Citation(
                source_url="https://example.com/article",
                evidence_snippet="the company."  # Last words
            )],
            confidence=0.9,
        ),
        evidence="News from the company.",
        item_url="https://example.com/article",
        expected_failures=(),  # Should pass
    ))

    # Case 28: Very short snippet (1 word)
    cases.append(SummaryCheckCase(
        case_id="edge_short_snippet",
        result=SummaryResult(
            summary="Profit was reported.",
            tags=["finance"],
            citations=[Citation(
                source_url="https://example.com/article",
                evidence_snippet="Profit"  # Just one word
            )],
            confidence=0.7,
        ),
        evidence="Profit was reported.",
        item_url="https://example.com/article",
        expected_failures=(),  # Should pass
    ))
    
    # Case 29: Unicode in evidence and snippet
    cases.append(SummaryCheckCase(
        case_id="edge_unicode",
        result=SummaryResult(
            summary="International news.",
            tags=["international"],
            citations=[Citation(
                source_url="https://example.com/article",
                evidence_snippet="日本語テスト"  # Japanese
            )],
            confidence=0.8,
        ),
        evidence="International report: 日本語テスト confirmed.",
        item_url="https://example.com/article",
        expected_failures=(),  # Should pass
    ))
    
    # Case 30: Whitespace handling
    cases.append(SummaryCheckCase(
        case_id="edge_whitespace",
        result=SummaryResult(
            summary="Spaced out.",
            tags=["test"],
            citations=[Citation(
                source_url="https://example.com/article",
                evidence_snippet="multiple   spaces"  # Multiple spaces
            )],
            confidence=0.6,
        ),
        evidence="Text with multiple   spaces included.",
        item_url="https://example.com/article",
        expected_failures=(),  # Should pass (exact match)
    ))

    # -------------------------------------------------------------------------
    # SUMMARY LENGTH
    # -------------------------------------------------------------------------

    # Case 31: Valid summary length (passes)
    cases.append(SummaryCheckCase(
        case_id="valid_summary_length",
        result=SummaryResult(
            summary="This is a valid summary that is long enough.",
            tags=["test"],
            citations=[Citation(
                source_url="https://example.com/article",
                evidence_snippet="valid summary"
            )],
            confidence=0.9,
        ),
        evidence="This is a valid summary that is long enough.",
        item_url="https://example.com/article",
        expected_failures=(),
    ))

    # Case 32: Summary too short (fails)
    cases.append(SummaryCheckCase(
        case_id="summary_too_short",
        result=SummaryResult(
            summary="Short",  # Only 5 characters!
            tags=["test"],
            citations=[Citation(
                source_url="https://example.com/article",
                evidence_snippet="Short"
            )],
            confidence=0.9,
        ),
        evidence="Short text here.",
        item_url="https://example.com/article",
        expected_failures=(SUMMARY_TOO_SHORT,),
    ))
    
    # Verify we have at least 30 cases
    assert len(cases) >= 32, f"Expected at least 30 cases, got {len(cases)}"

    return cases
"""
Summary evaluation failure taxonomy.

Each code represents a specific, actionable failure reason.
Codes are returned by check functions - never raised as exceptions.

INVARIANT: Eval checks only observe and report. They never modify data.
"""

# -----------------------------------------------------------------------------
# Schema Failures
# -----------------------------------------------------------------------------
SCHEMA_INVALID = "SCHEMA_INVALID"
# Pydantic validation failed (shouldn't happen if data came from our pipeline)

# -----------------------------------------------------------------------------
# Citation Failures (when summary is present)
# -----------------------------------------------------------------------------
MISSING_CITATIONS = "MISSING_CITATIONS"
# Summary exists but citations list is empty

SNIPPET_NOT_GROUNDED = "SNIPPET_NOT_GROUNDED"
# citation.evidence_snippet is not an exact substring of evidence

URL_MISMATCH = "URL_MISMATCH"
# citation.source_url does not match the item's URL

# -----------------------------------------------------------------------------
# Refusal Failures (when refusal is present)
# -----------------------------------------------------------------------------
INVALID_REFUSAL_CODE = "INVALID_REFUSAL_CODE"
# refusal string is not in the allowed set

# -----------------------------------------------------------------------------
# Tag Failures
# -----------------------------------------------------------------------------
NO_TAGS = "NO_TAGS"
# Summary present but tags list is empty

TOO_MANY_TAGS = "TOO_MANY_TAGS"
# More than MAX_TAGS (5) tags present

SUMMARY_TOO_SHORT = "SUMMARY_TOO_SHORT"
# Summary text is less than MIN_SUMMARY_LENGTH characters

# -----------------------------------------------------------------------------
# Valid Refusal Codes (for INVALID_REFUSAL_CODE check)
# -----------------------------------------------------------------------------
VALID_REFUSAL_CODES = frozenset({
    "LLM_PARSE_FAIL",
    "LLM_API_FAIL",
    "LLM_DISABLED",
    "NO_EVIDENCE",
    "GROUNDING_FAIL",
    "PIPELINE_ERROR",
})

# -----------------------------------------------------------------------------
# Constraints (configurable thresholds)
# -----------------------------------------------------------------------------
MAX_TAGS = 5
MIN_TAGS = 1
MIN_SUMMARY_LENGTH = 10
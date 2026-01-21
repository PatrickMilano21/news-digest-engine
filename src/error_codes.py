"""Stable failure codes for fetch and parse operations.

Used by: rss_fetch, daily_run, logging, run_failures table, /debug/run endpoint.
"""

FETCH_TIMEOUT = "FETCH_TIMEOUT"
FETCH_TRANSIENT = "FETCH_TRANSIENT"
RATE_LIMITED = "RATE_LIMITED"
FETCH_PERMANENT = "FETCH_PERMANENT"
PARSE_ERROR = "PARSE_ERROR"

  # LLM codes
LLM_PARSE_FAIL = "LLM_PARSE_FAIL"      # JSON didn't match schema after retry
LLM_API_FAIL = "LLM_API_FAIL"          # Timeout, 429, network error
LLM_DISABLED = "LLM_DISABLED"          # No API key configured
NO_EVIDENCE = "NO_EVIDENCE"            # Stubbed for Day 16 grounding
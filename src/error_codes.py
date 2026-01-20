"""Stable failure codes for fetch and parse operations.

Used by: rss_fetch, daily_run, logging, run_failures table, /debug/run endpoint.
"""

FETCH_TIMEOUT = "FETCH_TIMEOUT"
FETCH_TRANSIENT = "FETCH_TRANSIENT"
RATE_LIMITED = "RATE_LIMITED"
FETCH_PERMANENT = "FETCH_PERMANENT"
PARSE_ERROR = "PARSE_ERROR"
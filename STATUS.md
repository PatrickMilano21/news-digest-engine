# Project Status — News Digest Engine

## Current Day
Day 11 (Week 2) — 2026-01-19

## Today Shipped
- Created `src/error_codes.py` with failure taxonomy
  - `FETCH_TIMEOUT`, `FETCH_TRANSIENT`, `RATE_LIMITED`, `FETCH_PERMANENT`, `PARSE_ERROR`
- Refactored `src/rss_fetch.py` for structured results
  - Added `FetchResult` dataclass (ok, content, error_code, error_message)
  - `fetch_rss_with_retry()` now returns `FetchResult` instead of raising
  - 429 returns immediately (no retry), 5xx/timeout retry with backoff
- Rewrote `jobs/daily_run.py` with graceful ingestion loop
  - Loops over feeds, handles failures, continues on errors
  - Failures logged, classified, counted, stored in `run_failures`
  - One feed failing never aborts the whole run
- Created `src/feeds.py` with hardcoded feed URLs
- Consolidated normalization logic in `src/normalize.py`
  - Moved `normalize_url()`, `normalize_title()`, `dedupe_key()` from schemas.py
  - `normalize_url()` now strips tracking params (utm_*, fbclid, gclid, etc.)
  - Lowercases scheme + hostname
  - Sorts query params for consistent deduplication
- Cleaned up `src/schemas.py` to contain only data models (NewsItem, IngestRequest)
- Added operator-grade `run_end` logging
  - Unified event schema for both ingest and eval runs
  - Fields: `run_id`, `run_type`, `status`, `elapsed_ms`, `failures_by_code`, `counts`
  - Ingest counts: `received`, `after_dedupe`, `inserted`, `duplicates`
  - Eval counts: `total`, `passed`, `failed` + `artifact_paths`
  - One log line per run for grep-friendly monitoring

## Tests
- Updated: 3 tests in `test_rss_fetch.py` for `FetchResult` behavior
  - `test_fetch_rss_with_retry_429_returns_rate_limited`
  - `test_fetch_rss_with_retry_exhausted_returns_transient`
  - `test_fetch_rss_with_retry_backoff`
- Added: 4 tests in `test_normalize.py` for URL canonicalization
  - `test_normalize_url_strips_tracking_params`
  - `test_normalize_url_sorts_params`
  - `test_normalize_url_lowercases_scheme_and_host`
  - `test_dedupe_key_same_for_tracking_variants`
- Current: all passing (`make test`)

## Current Blockers
- None

## Next (Day 12)
1. Integration test for daily_run with mocked feeds
2. Add more feeds to config
3. End-to-end run validation with real feeds

## Commands (known-good)
- Activate venv: `.\.venv\Scripts\Activate.ps1`
- Tests: `make test`
- Dev: `make dev`
- Daily run: `python -m jobs.daily_run --date 2026-01-19`
- Eval: `make eval DATE=2026-01-15`
- Query runs: `curl http://localhost:8000/runs/latest`
- Debug run: `curl http://localhost:8000/debug/run/{run_id}`

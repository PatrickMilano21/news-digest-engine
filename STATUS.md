# Project Status — News Digest Engine

## Current Day
Day 11 (Week 2) — 2026-01-19

## Today Shipped
- Made `run_type` explicit in the database schema
  - Added `run_type TEXT NOT NULL DEFAULT 'ingest'` to runs table
  - Added idempotent migration for existing DBs (ALTER TABLE if column missing)
- Updated repo layer with clear semantics:
  - `start_run()` accepts `run_type` parameter (default `'ingest'`)
  - `get_run_by_day()` now filters to `run_type='ingest'` only
  - `get_run_by_id()` now returns `run_type` in dict
  - Added `get_eval_run_by_day()` — filters to `run_type='eval'`
  - Added `list_runs_by_day()` — returns all runs (debug tooling)
- Updated `src/eval.py` to pass `run_type='eval'` explicitly
- Enhanced `/debug/run/{run_id}` to return `run_type` in response
- Renamed `test_day7_demo_flow.py` → `test_demo_flow.py`

## Tests
- Added: 3 new tests for run_type behavior
  - `test_start_run_stores_run_type`
  - `test_get_run_by_day_returns_ingest_only`
  - `test_get_eval_run_by_day_returns_eval_only`
- Updated: `test_debug_run_returns_breakdown_and_artifacts` (asserts run_type)
- Current: all passing (`make test`)

## Current Blockers
- None

## Next (highest leverage)
1) Reliability pass — retry policy for RSS fetch, rate limiting
2) Artifact persistence verification (digest + eval both recorded)
3) End-to-end flow validation with new run_type semantics

## Commands (known-good)
- Activate venv: `.\.venv\Scripts\Activate.ps1`
- Tests: `make test`
- Dev: `make dev`
- Eval: `make eval DATE=2026-01-15`
- Query runs: `curl http://localhost:8000/runs/latest`
- Debug run: `curl http://localhost:8000/debug/run/{run_id}`

# Project Status — News Digest Engine

## Current Day
**Day 13** (Week 2) — 2026-01-20

## Today Shipped

### PII Redaction Layer (`src/redact.py`)
- `redact(text)` — regex replacement for emails and phones
- `sanitize(obj)` — recursive walker for nested dicts/lists
- Patterns: `EMAIL_PATTERN`, `PHONE_PATTERN`
- Safety boundary before any data hits audit logs

### Audit Logs (`src/db.py` + `src/repo.py`)
- New table: `audit_logs` (id, ts, event_type, run_id, day, details_json)
- `write_audit_log()` — best-effort write, never raises, auto-sanitizes PII
- `get_audit_logs()` — read for debugging
- Event types: `RUN_STARTED`, `RUN_FINISHED_OK`, `RUN_FINISHED_ERROR`, `DIGEST_GENERATED`

### Weekly Report (`src/weekly_report.py`)
- `write_weekly_report(conn, end_day, days=7)` — generates `artifacts/weekly_report.md`
- Sections: Top Sources, Boost Config, Eval Pass Rate, Run Failures
- `_parse_eval_pass_rate()` — best-effort parsing (returns "N/A" on failure)

### Aggregate Queries (`src/repo.py`)
- `report_top_sources(conn, end_day, days, limit)` — item counts by source
- `report_failures_by_code(conn, end_day, days)` — run failures by error_type
- Uses `DATE()` for safe timestamp comparison

### Pipeline Integration (`jobs/daily_run.py`)
- Audit events wired in: RUN_STARTED, RUN_FINISHED_OK, RUN_FINISHED_ERROR
- Weekly report generated after successful runs (best-effort, won't crash pipeline)

## Tests
- Command: `make test`
- Result: 101 passed
- New tests: `test_redact.py`, `test_audit.py`, `test_weekly_report.py`, aggregate query tests

## Known Limitations (Documented)
- Boost config shows current settings, not historical per-run
- Eval pass rate only checks end_day, not aggregated weekly

## Current Blockers
- None

## Next (Day 14+)
1. 90-min timed drill: customer bugfix (failing tests + broken endpoint)
2. Week 3: MCP as intelligence boundary (LLM grounding)
3. Consider storing config snapshot per run for historical accuracy

## Key Learnings
- Audit logging must be best-effort — never crash the pipeline for logging
- `sanitize()` recursive pattern handles nested PII in any structure
- Separation: schema in `db.py`, queries in `repo.py`, business logic in dedicated modules
- "Minimum enterprise posture" = redact + audit + report, not a full platform

## Commands (known-good)
- Activate venv: `.\.venv\Scripts\Activate.ps1`
- Tests: `make test`
- Dev: `make dev`
- Daily run: `python -m jobs.daily_run --date 2026-01-20`
- Eval: `make eval DATE=2026-01-20`
- Query runs: `curl http://localhost:8000/runs/latest`
- Debug run: `curl http://localhost:8000/debug/run/{run_id}`
- Query audit logs: `SELECT * FROM audit_logs ORDER BY id DESC LIMIT 10;`
- MCP list: `claude mcp list`

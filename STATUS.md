# Project Status — News Digest Engine

## Current Day
Day 09 (Week 2) — 2026-01-17

## Today Shipped
- Updated CLAUDE.md with "Code suggestions vs file edits" section
- Added FILE_EDIT_MODE: ON/OFF and EDIT_ONLY unlock phrases
- Added explicit default mode declaration (FILE_EDIT_MODE: OFF)
- Added DOCS_ONLY trigger for safe admin edits
- Clarified YOUR MOVE as Patrick's responsibility

## Tests
- Added/updated: 0 (docs-only session)
- Current: unknown (run `make test` to verify)

## Current Blockers
- Day 9 code work not started (eval report artifact, failure taxonomy wiring)

## Next (highest leverage)
1) Wire taxonomy into `evals/runner.py` (error_code classification)
2) Add failure breakdown by code to `run_all()`
3) Create `artifacts/eval_report_YYYY-MM-DD.md` generator

## Commands (known-good)
- Activate venv: `.\.venv\Scripts\Activate.ps1`
- Tests: `make test`
- Dev: `make dev`
- Eval: `make eval DATE=2025-01-15`

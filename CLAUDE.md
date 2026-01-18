# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Always read this file first. Do not rely on chat memory.**

## Project Overview

News Digest Engine is a FastAPI service that ingests RSS feeds, normalizes/deduplicates items, ranks them deterministically, and produces HTML digests with explainability.

**Goal:** Demonstrate FDE / Applied / Solutions engineering by shipping a deterministic, test-driven backend:

```
Ingest → normalize/dedupe → rank → artifacts → run history → evals → (later) LLM grounding + citations
```

**Primary repo:** `news-digest-engine`
**Gym repo:** `fde-drills`

### Non-negotiables
- Deterministic + test-driven
- Debuggable + boring competence
- No scope creep while tests are red
- Strict build protocol

## Reference Documents (`docs/raw/` - READ ONLY)

| File | Purpose | Authority |
|------|---------|-----------|
| `AI Job Pivot Handoff_ Source of Truth.docx` | Build protocol / how we work | AUTHORITATIVE — wins on process |
| `Locked_Syllabus.docx` | Day-by-day tasks, DoD, required artifacts | AUTHORITATIVE — no invented scope |
| `Locked_Portfolio_v1.docx` | Role targeting (OpenAI FDE), tradeoff justification | AUTHORITATIVE |
| `LinkedIN Profile.docx` | External narrative, recruiter language | REFERENCE only |

## Operating Rules (for assistants)

- Treat `docs/raw/` as read-only (do not edit .docx files).
- Start work by reading `CLAUDE.md` and then checking `docs/raw/Locked_Syllabus.docx` for the next incomplete day.
- When coding, follow: **English spec → YOUR MOVE → reference**
  - **English spec:** what/why/acceptance + files touched
  - **YOUR MOVE:** you implement + run `make test` + paste first failing output
  - **Reference:** provide minimal diffs only after the attempt; no refactors unless requested
- Mini-steps only: one small testable change; ask exactly one mechanical check-in question per step.
- Keep tests green. If red: fix the smallest failing thing only.
- End each step with: what changed, commands to run, and what "green" looks like.
- When a module name changes, update the Architecture section in the same commit.

## Common Commands

```powershell
# Run tests
make test

# Run single test
.\.venv\Scripts\python.exe -m pytest tests/test_scoring.py -q

# Start dev server (port 8000 with reload)
make dev

# Run daily job for a specific date
make run DATE=2025-01-15

# Run evaluation harness
make eval DATE=2025-01-15
```

## Architecture

### Data Flow
```
RSS XML → rss_fetch.py → rss_parse.py → normalize.py → repo.py (SQLite)
                                              ↓
                        scoring.py ← get_news_items_by_date()
                              ↓
                        explain.py → artifacts.py → HTML digest
```

### Key Modules

- **`src/main.py`**: FastAPI app with endpoints `/ingest/raw`, `/rank/{date}`, `/digest/{date}`, `/runs/latest`
- **`src/schemas.py`**: `NewsItem` model + normalization functions (`normalize_url`, `normalize_title`, `dedupe_key`)
- **`src/scoring.py`**: `RankConfig` model + `rank_items()` - deterministic ranking by score → timestamp → index
- **`src/repo.py`**: SQLite CRUD for `news_items` and `runs` tables
- **`jobs/daily_run.py`**: CLI for daily batch job with idempotency (skips if run exists for day)
- **`jobs/build_digest.py`**: Generates HTML digest artifacts

### Database

SQLite at `data/news.db` (overridden via `NEWS_DB_PATH` env var in tests).

**Tables:**
- `news_items`: `dedupe_key` (UNIQUE), source, url, published_at, title, evidence
- `runs`: run_id (PK), started_at, finished_at, status, metrics, error fields

### Repo Layer (`src/repo.py`)

All database access goes through these functions:

**news_items:**
- `insert_news_items(conn, items)` → `{inserted, duplicates}` - bulk insert with INSERT OR IGNORE
- `get_news_items_by_date(conn, day=)` → `list[NewsItem]` - fetch items for a YYYY-MM-DD day

**runs:**
- `start_run(conn, run_id, started_at, received)` - create new run record
- `finish_run_ok(conn, run_id, finished_at, *, after_dedupe, inserted, duplicates)` - mark success
- `finish_run_error(conn, run_id, finished_at, *, error_type, error_message)` - mark failure
- `get_latest_run(conn)` → `dict | None` - most recent run
- `get_run_by_day(conn, day=)` → `dict | None` - most recent run for a day
- `get_run_by_id(conn, run_id=)` → `dict | None` - lookup by ID
- `has_successful_run_for_day(conn, day=)` → `bool` - idempotency check
- `report_runs_by_day(conn, limit=7)` → `list[dict]` - aggregated daily stats

### Deduplication

SHA256 of `normalized_url|normalized_title` produces stable `dedupe_key`. Python-level dedupe happens first, then DB-level via UNIQUE constraint.

### Ranking Algorithm

```python
score = (topic_matches + keyword_boosts) × source_weight × recency_decay
```

Ties broken by: score desc → published_at desc → original index asc

## Testing

Tests use isolated temp SQLite via `conftest.py` autouse fixture that sets `NEWS_DB_PATH`. All tests are deterministic with fixed timestamps and fixture data.

## Operability Conventions

- All responses include `X-Request-ID` header
- Errors return RFC 7807 ProblemDetails JSON
- Structured JSON logging via `log_event()`
- Run tracking: every operation gets a `run_id` with start/finish timestamps and metrics

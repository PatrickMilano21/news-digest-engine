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
  - **YOUR MOVE (Patrick):** I implement + run `make test` + paste first failing output
  - **Reference:** provide minimal diffs only after the attempt; no refactors unless requested
- Mini-steps only: one small testable change; ask exactly one mechanical check-in question per step.
- Keep tests green. If red: fix the smallest failing thing only.
- End each step with: what changed, commands to run, and what "green" looks like.
- When a module name changes, update the Architecture section in the same commit.

## Code suggestions vs file edits (IMPORTANT)

Default behavior:
- You MAY provide code snippets in the chat (reference snippets / minimal diffs).
- You MUST NOT write or modify code files in the repo unless explicitly unlocked.

File edit unlock phrases:
- **FILE_EDIT_MODE: ON** (you may edit code files)
- **FILE_EDIT_MODE: OFF** (return to chat-only suggestions)
- **EDIT_ONLY: <path>** (permission to edit exactly one file)

Even when giving code snippets:
- Follow English spec → YOUR MOVE → reference
- Do not dump full solutions upfront
- Provide only the mini-step snippet, not multi-step combined code

Current mode (default): **FILE_EDIT_MODE: OFF**
Unless I explicitly switch modes, you may only provide chat snippets and must not edit repo files.

## End-of-day workflow (git + status)

At the end of a day:
1) Update `STATUS.md` with:
   - Day number + date
   - Shipped features (bullets)
   - Tests added/updated (count)
   - Remaining blockers
   - Next day target
2) Prepare a commit plan:
   - Show `git status` summary
   - Propose the exact `git add` paths (never `git add -A`)
   - Propose a commit message: `dayXX: <tight summary>`
3) DO NOT run `git commit` automatically.
   - I (Patrick) will run the final commands.
4) Never stage/commit:
   - `.claude/`, `.env`, `data/`, secrets, large artifacts
5) **Claude must never run git commands.** All git is executed manually in a separate terminal.

## Trigger: END_OF_DAY DayXX

When I say: **END_OF_DAY DayXX**

Do not modify code files. Only update `STATUS.md` and output git commands.

Claude must:
1) Create/update `STATUS.md` (repo root) with:
   - Current Day (DayXX + date)
   - Today Shipped
   - Tests (command + pass/fail)
   - Current Blockers
   - Next (top 3)
   - Commands (known-good)
2) Print sanity checks (yes/no):
   - STATUS.md updated today
   - Exactly one commit planned (unless hotfix)
   - Commit message starts with `dayXX:`
   - Tests green right now (if unknown, say NO and show command)
3) Output git plan as commands only (do not execute):
   - `git status`
   - `git diff`
   - `git add <explicit paths>` (never `git add -A`)
   - `git commit -m "dayXX: <tight summary>"`

Constraints:
- Never stage/commit: `.claude/`, `.env*`, `data/`, secrets, large artifacts.
- If tests are red/unknown, stop at git plan and tell me the smallest next step to get green.

## Trigger: DOCS_ONLY

When I say: **DOCS_ONLY**
- You may edit only: `CLAUDE.md`, `STATUS.md`, and markdown files under `docs/` or `writeups/`.
- Do not modify any code files.

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

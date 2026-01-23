# Project Status — News Digest Engine

## Current Day
**Day 18** (Week 3) — 2026-01-23 (COMPLETE)

## Today: Pipeline Integration + Idempotency + Safe Failure

### Goal
Robust feedback system with idempotency protection, consistent error responses, and safe failure patterns.

### Completed Steps

#### Step 18.5: Feedback System with Idempotency ✓
- Added 3 new tables: `idempotency_keys`, `run_feedback`, `item_feedback`
- Created `RunFeedbackRequest`, `ItemFeedbackRequest` schemas
- Added repo functions: `upsert_run_feedback`, `upsert_item_feedback`, `get_run_feedback`, `get_item_feedback`
- Added endpoints: `POST /feedback/run`, `POST /feedback/item`
- Idempotency via `X-Idempotency-Key` header

#### Step 18.6: Standardize Error Responses ✓
- Added `RequestValidationError` exception handler
- All errors return ProblemDetails format (status, code, message, request_id)
- 422 validation errors include field location in message

#### Step 18.7: Request ID Propagation ✓
- Audited all endpoints for X-Request-ID header
- Confirmed middleware sets header on all responses

#### Step 18.8: Error Shape Tests ✓
- `test_404_error_returns_problem_details`
- `test_500_error_returns_problem_details_no_leak`
- `test_different_idempotency_keys_processed_separately`

#### Step 18.9: Timed Drills ✓
- **Drill A (Silent Failure):** Found typo `run_feedbak` + bare `except: return 0`
- **Drill C (Race Condition):** Found idempotency check AFTER processing instead of BEFORE
- Added `test_idempotency_skips_processing_on_second_request` to catch timing bugs

### Files Created/Modified (Day 18)
- `src/db.py` (MODIFIED - added idempotency_keys, run_feedback, item_feedback tables)
- `src/schemas.py` (MODIFIED - added RunFeedbackRequest, ItemFeedbackRequest)
- `src/repo.py` (MODIFIED - added upsert/get feedback functions, fixed indentation)
- `src/main.py` (MODIFIED - added feedback endpoints, validation handler, fixed imports)
- `tests/test_feedback.py` (NEW - 14 tests)

### Key Design Decisions (Day 18)
- **UPSERT for feedback** — user can change rating, same row updated
- **Composite UNIQUE (run_id, item_url)** — one feedback per item per run
- **Idempotency key is client-generated** — random UUID, not derived from data
- **Check idempotency BEFORE processing** — order matters for correctness
- **Never use bare `except:`** — hides bugs like typos

### Key Concepts Learned
- **UPSERT** — `ON CONFLICT DO UPDATE` for insert-or-update in one statement
- **Idempotency flow** — check → process → store (order matters!)
- **Silent failures** — bare except + typos = bugs that hide
- **Testing behavior vs output** — use monkeypatch to count function calls
- **422 vs 400** — 422 for validation errors, 400 for malformed requests
- **Frontend generates idempotency keys** — new key per user action, same key for retries

## Tests
- Command: `make test`
- Result: 175 passed

## Current Blockers
- None

## Day 17 Summary (Completed)
- LLM caching with cache key strategy
- `compute_cache_key()`, `summary_cache` table
- Cache hits/misses logging and stats
- 157 tests passed

## Day 16 Summary (Completed)
- Grounding + strict citations enforcement
- `validate_grounding()` with exact substring match
- 127 tests passed

## Next (Day 19)
- TBD (check syllabus)

## Commands (known-good)
- Activate venv: `.\.venv\Scripts\Activate.ps1`
- Tests: `make test`
- Dev: `make dev`
- Daily run: `make run DATE=2026-01-23`
- Eval: `make eval DATE=2026-01-23`
- Query runs: `curl http://localhost:8000/runs/latest`
- Debug run: `curl http://localhost:8000/debug/run/{run_id}`
- UI: `http://localhost:8000/ui/date/2026-01-23`
- Feedback: `curl -X POST http://localhost:8000/feedback/run -H "Content-Type: application/json" -d '{"run_id":"...", "rating":5}'`

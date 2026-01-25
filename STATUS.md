# Project Status — News Digest Engine

## Current Day
**Day 20** (Week 3) — 2026-01-25

## Today: Code Review + Refactoring + Test Coverage

### Goal
Review all Day 20 changes, add missing tests, clean up code organization, document patterns.

### Completed Steps

#### Test Coverage
- Added 11 new tests for Tasks #1-#12 features
- Failed sources tracking: 5 tests
- /debug/stats scoping: 2 tests
- Evals in pipeline: 3 tests
- LLM disabled logging: 1 test
- Total: 201 tests passing

#### Code Cleanup
- Removed redundant `get_run_failures_breakdown()` function
- Extracted display logic from `main.py` to new `src/views.py`
- Route handlers now thin — delegate to views.py for presentation

#### Documentation
- Updated CLAUDE.md with views.py in all relevant sections
- Created future.md for planned future work

### Files Created/Modified (Day 20)
- `src/views.py` (NEW — display/presentation logic)
- `src/main.py` (MODIFIED — simplified, uses views.py)
- `src/repo.py` (MODIFIED — removed redundant function)
- `tests/test_demo_flow.py` (MODIFIED — added 2 tests)
- `tests/test_pipeline.py` (MODIFIED — added 4 tests)
- `tests/test_repo.py` (MODIFIED — added 5 tests, updated 1)
- `CLAUDE.md` (MODIFIED — documented views.py pattern)
- `future.md` (NEW — future work planning)

### Key Design Decisions (Day 20)
- **views.py for display logic** — UI changes don't require editing routes
- **Remove redundant functions** — get_run_failures_with_sources supersedes breakdown-only version
- **Test behavior, not implementation** — use getter functions, not raw SQL in tests

### Tests
- Command: `make test`
- Result: 201 passed

## Current Blockers
- None

## Next
- Task #11: Per-user RankConfig customization (future scope)
- Consider more UI improvements
- Production deployment preparation

## Commands (known-good)
- Activate venv: `.\.venv\Scripts\Activate.ps1`
- Tests: `make test`
- Dev: `make dev`
- Daily run: `make run DATE=2026-01-25`
- Eval: `make eval DATE=2026-01-25`
- Query runs: `curl http://localhost:8000/runs/latest`
- Debug run: `curl http://localhost:8000/debug/run/{run_id}`
- UI: `http://localhost:8000/`

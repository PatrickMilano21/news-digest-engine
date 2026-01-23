# Project Status — News Digest Engine

## Current Day
**Day 19** (Week 3) — 2026-01-23 (COMPLETE)

## Today: Eval v1 — Summary Quality Checks

### Goal
Build deterministic eval system for summary quality: citations, grounding, tags, refusals.

### Completed Steps

#### Step 19.1: Summary Taxonomy ✓
- Created `evals/summary_taxonomy.py` with failure codes
- Codes: `SCHEMA_INVALID`, `MISSING_CITATIONS`, `SNIPPET_NOT_GROUNDED`, `URL_MISMATCH`, `INVALID_REFUSAL_CODE`, `NO_TAGS`, `TOO_MANY_TAGS`, `SUMMARY_TOO_SHORT`
- Constants: `VALID_REFUSAL_CODES`, `MAX_TAGS=5`, `MIN_TAGS=1`, `MIN_SUMMARY_LENGTH=10`

#### Step 19.2: Summary Check Functions ✓
- Created `evals/summary_checks.py` with 7 check functions
- Each returns failure code or None (pure functions, no side effects)
- Fixed 4 bugs: `if` → `for` loops, missing colon, `return` in append

#### Step 19.3: Summary Test Cases ✓
- Created `evals/summary_cases.py` with 32 test cases
- Categories: valid summaries, valid refusals, missing citations, bad grounding, URL mismatch, invalid refusal, tag issues, multiple failures, edge cases, summary length

#### Step 19.4: Summary Runner ✓
- Created `evals/summary_runner.py` with `run_case()`, `run_all_cases()`, `summarize_results()`
- Fixed 2 bugs: wrong import, wrong field name

#### Step 19.5: Verified 100% Pass Rate ✓
- All 32 summary check cases pass

#### Step 19.6: Combined Eval Report ✓
- Modified `evals/runner.py` to include summary evals in same report
- Report now shows: Ranking Evals (50) + Summary Quality Evals (32)
- Added timestamp, run_id, overall combined stats

#### Step 19.7: Pipeline Integration ✓
- Modified `src/eval.py` to print both eval results
- Console shows: ranking, summary, overall pass rates
- JSON log includes all counts

#### Step 19.8: Tests for Summary Checks ✓
- Created `tests/test_summary_eval_harness.py`
- Tests: load cases, all pass, summarize math, check_summary_length

#### Step 19.9: Timed Drill ✓
- Added `check_summary_length()` — fails if summary < 10 chars
- Added `SUMMARY_TOO_SHORT` error code
- Added 2 test cases + 3 unit tests

### Files Created/Modified (Day 19)
- `evals/summary_taxonomy.py` (NEW — failure codes + constants)
- `evals/summary_checks.py` (NEW — 7 check functions)
- `evals/summary_cases.py` (NEW — 32 test cases)
- `evals/summary_runner.py` (NEW — case runner + summarizer)
- `evals/runner.py` (MODIFIED — combined report with summary evals)
- `src/eval.py` (MODIFIED — print both eval types)
- `tests/test_summary_eval_harness.py` (NEW — 6 tests)

### Key Design Decisions (Day 19)
- **Evals are pure functions** — observe and report, never modify
- **Failure codes not exceptions** — return strings, not raise
- **Combined report** — one file with all eval types
- **Fixture-driven testing** — predefined inputs + expected outputs
- **Compare as sets** — order of failures doesn't matter

### Key Concepts Learned
- **Eval vs Enforcement** — evals measure, pipeline enforces
- **Pure functions** — no side effects, deterministic
- **frozenset** — immutable set for constants
- **Multiple failure collection** — return list of all failures, not just first
- **Meta-testing** — testing that our checks work correctly

## Tests
- Command: `make test`
- Result: 181 passed

## Current Blockers
- None

## Day 18 Summary (Completed)
- Feedback system with idempotency
- UPSERT pattern, idempotency keys
- ProblemDetails error format
- 175 tests passed

## Day 17 Summary (Completed)
- LLM caching with cache key strategy
- 157 tests passed

## Next (Day 20)
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

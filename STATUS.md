# Project Status — News Digest Engine

## Current Day
**Day 17** (Week 3) — 2026-01-22 (COMPLETE)

## Today: Caching + Cost/Latency Guardrails

### Goal
We never pay twice for the same LLM work, and we can explain exactly what each run cost.

### Completed Steps

#### Step 17.1: Cache Key Strategy ✓
- Created `src/cache_utils.py` with `compute_cache_key(model, evidence)`
- Cache key = SHA256(model + "|" + normalized_evidence)
- Tests in `tests/test_cache_utils.py` (normalization, determinism, collision prevention)

#### Step 17.2: Database Table ✓
- Added `summary_cache` table to `src/db.py`
- Columns: cache_key (PK), model_name, summary_json, prompt_tokens, completion_tokens, cost_usd, latency_ms, created_at
- Tests in `tests/test_summary_cache_table.py`

#### Step 17.3: Repo Layer ✓
- Added `get_cached_summary(conn, cache_key)` → dict | None
- Added `insert_cached_summary(conn, ...)` with INSERT OR IGNORE
- Tests in `tests/test_summary_cache_repo.py`

#### Step 17.4: Return Usage from summarize() ✓
- Changed `summarize()` to return `tuple[SummaryResult, dict]`
- Usage dict contains: prompt_tokens, completion_tokens, cost_usd, latency_ms
- Updated `_refuse()` to return zeros when no API call made
- Updated all tests in `tests/test_llm_openai.py` to unpack tuple

#### Step 17.5: Integrate Cache into Pipeline ✓
- Updated `jobs/build_digest.py` with cache logic
- Fixed bug: `usage["prompt tokens"]` → `usage["prompt_tokens"]`
- Fixed bug: `summaries.append(validated)` → `summaries.append(result)`

#### Step 17.6: Add Logging for Cache Hits/Misses ✓
- Added `log_event("llm_cache_hit", ...)` with saved_cost_usd, saved_latency_ms
- Added `log_event("llm_cache_miss", ...)` with cost_usd, latency_ms, was_cached

#### Step 17.7: Run-Level Stats Aggregation ✓
- Added `llm_stats` dict to track totals across run
- Tracks: cache_hits, cache_misses, total_prompt_tokens, total_completion_tokens, total_cost_usd, saved_cost_usd
- Added `log_event("run_llm_stats", **llm_stats)` after loop

#### Step 17.8: Write Cache Behavior Tests ✓
- Created `tests/test_cache_behavior.py` with 5 tests:
  - `test_cache_hit_skips_llm_call`
  - `test_cache_miss_calls_llm`
  - `test_successful_result_cached`
  - `test_refusal_not_cached`
  - `test_grounding_fail_not_cached`

#### Step 17.9: TTL Drill (Bonus) ✓
- Added `is_cache_expired(created_at, ttl_seconds, now)` to `src/cache_utils.py`
- Added 4 TTL tests to `tests/test_cache_utils.py`
- Not wired into pipeline (drill for practice)

#### Step 17.10: Update STATUS.md ✓

### Files Created/Modified (Day 17)
- `src/cache_utils.py` (NEW - compute_cache_key, normalize_evidence, is_cache_expired)
- `tests/test_cache_utils.py` (NEW - 15 tests)
- `src/db.py` (MODIFIED - added summary_cache table)
- `tests/test_summary_cache_table.py` (NEW - 3 tests)
- `src/repo.py` (MODIFIED - get_cached_summary, insert_cached_summary)
- `tests/test_summary_cache_repo.py` (NEW - 5 tests)
- `src/clients/llm_openai.py` (MODIFIED - returns tuple, added _compute_cost)
- `tests/test_llm_openai.py` (MODIFIED - unpack tuples, verify usage)
- `jobs/build_digest.py` (MODIFIED - cache integration, logging, stats)
- `tests/test_cache_behavior.py` (NEW - 5 tests)

### Key Design Decisions (Day 17)
- **Cache key = model + evidence only** (not title/URL) — aligns with grounding rule
- **Cache after grounding validation** — only cache trustworthy results
- **Never cache refusals** — they might be transient (retry might work)
- **Return tuple from summarize()** — keeps SummaryResult clean, separates domain from ops
- **INSERT OR IGNORE** — first write wins, cache entries immutable
- **Pass `now` as parameter** — testability, determinism, no hidden side effects

### Key Concepts Learned
- **conftest.py autouse fixture** — automatically isolates every test with temp DB
- **Tuple unpacking** — `(value)` is not a tuple, `(value,)` is
- **Caching belongs after trust** — LLM → parse → validate → cache (not before)
- **Patch where used, not where defined** — `monkeypatch.setattr("jobs.build_digest.summarize", ...)`
- **TTL boundary** — use `>=` because "exactly TTL old" means just expired

## Tests
- Command: `make test`
- Result: 157 passed

## Current Blockers
- None

## Day 16 Summary (Completed)
- Grounding + strict citations enforcement
- `validate_grounding()` with exact substring match
- GROUNDING_FAIL error code
- 127 tests passed

## Next (Day 18)
- TBD (check syllabus)

## Commands (known-good)
- Activate venv: `.\.venv\Scripts\Activate.ps1`
- Tests: `make test`
- Dev: `make dev`
- Daily run: `make run DATE=2026-01-22`
- Eval: `make eval DATE=2026-01-22`
- Query runs: `curl http://localhost:8000/runs/latest`
- Debug run: `curl http://localhost:8000/debug/run/{run_id}`
- UI: `http://localhost:8000/ui/date/2026-01-22`

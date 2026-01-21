# Project Status — News Digest Engine

## Current Day
**Day 15** (Week 3) — 2026-01-21

## Today Shipped

### LLM Adapter v0 (Schema-First, OpenAI-First)
- **Output schema:** `src/llm_schemas/summary.py` with `Citation` + `SummaryResult` models
- **Containment boundary:** `summarize()` never crashes, always returns valid `SummaryResult`
- **Error taxonomy:** `LLM_PARSE_FAIL`, `LLM_API_FAIL`, `LLM_DISABLED`, `NO_EVIDENCE`
- **Defensive JSON parser:** `src/json_utils.py` with `safe_parse_json()` (handles markdown fences)
- **Retry mechanism:** Parse → Retry with "fix JSON" prompt → Refuse
- **Cost/latency logging:** Every LLM call logged with tokens, cost_usd, latency_ms, status

### Files Created
- `src/llm_schemas/__init__.py` (package)
- `src/llm_schemas/summary.py` (Citation, SummaryResult)
- `src/json_utils.py` (safe_parse_json)
- `src/clients/__init__.py` (package)
- `src/clients/llm_openai.py` (summarize + helpers)
- `tests/test_json_utils.py` (9 tests)
- `tests/test_llm_openai.py` (9 tests)

### Key Design Decisions
- **Schema-first:** Define output contract before prompts; schema is the gate
- **Containment boundary:** Adapter never raises, always returns SummaryResult
- **Temperature 0.0:** Deterministic output for structured JSON extraction
- **No external deps:** Uses `urllib.request` only (no requests/httpx)
- **Refusal > corruption:** `safe_parse_json` returns None rather than guessing

## Tests
- Command: `make test`
- Result: 119 passed (was 110)

## Current Blockers
- None

## Next (Day 16 / Week 3)
1. Wire `summarize()` into pipeline (call from daily run)
2. Grounding validation (verify citations appear in evidence)
3. Config snapshots per run for historical accuracy

## Commands (known-good)
- Activate venv: `.\.venv\Scripts\Activate.ps1`
- Tests: `make test`
- Dev: `make dev`
- Daily run: `make run DATE=2026-01-21`
- Eval: `make eval DATE=2026-01-21`
- Query runs: `curl http://localhost:8000/runs/latest`
- Debug run: `curl http://localhost:8000/debug/run/{run_id}`
- UI: `http://localhost:8000/ui/date/2026-01-21`

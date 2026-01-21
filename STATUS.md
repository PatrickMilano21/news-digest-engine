# Project Status — News Digest Engine

## Current Day
**Day 16** (Week 3) — 2026-01-21

## Today Shipped

### Grounding + Strict Citations (Hard Pass/Fail)
- **Core principle:** LLM is not allowed to "know" things — only transform provided evidence
- **Grounding validator:** `src/grounding.py` with `validate_grounding()` enforces exact substring match
- **Error taxonomy:** Added `GROUNDING_FAIL` for hallucination detection (distinct from `LLM_PARSE_FAIL`)
- **Strict prompt:** Updated SYSTEM_PROMPT with explicit grounding rules (advisory layer)
- **Pipeline integration:** `build_digest.py` now calls summarize → validate → render
- **HTML rendering:** Summaries + citations displayed in digest (blue box), refusals shown (red box)

### Files Created/Modified
- `src/grounding.py` (NEW - validate_grounding function)
- `tests/test_grounding.py` (NEW - 8 tests)
- `src/llm_schemas/summary.py` (FIXED - validator logic was inverted)
- `src/error_codes.py` (ADDED - GROUNDING_FAIL)
- `src/clients/llm_openai.py` (UPDATED - strict grounding rules in prompt)
- `jobs/build_digest.py` (UPDATED - wired summarize + validate into pipeline)
- `src/artifacts.py` (UPDATED - render_summary, citations display)

### Key Design Decisions
- **Exact substring match:** `citation.evidence_snippet in evidence` — binary, auditable, no judgment
- **Refusal > corruption:** If any citation fails verification, entire result refused
- **Separate error codes:** `LLM_PARSE_FAIL` (wrong format) vs `GROUNDING_FAIL` (hallucination) — operationally different
- **Prompt is advisory, code is enforcement:** Prompt reduces failures, code catches all remaining

### Important Observations (Room for Improvement)
- **Prompt/evidence imbalance:** ~300 token prompt vs ~5-50 token evidence (RSS description only)
- **High refusal rate expected:** Correct behavior with thin evidence — will improve when full articles fetched
- **Evidence source:** Currently RSS `<description>` only, not full article text

## Tests
- Command: `make test`
- Result: 127 passed (was 119)

## Current Blockers
- None

## Next (Day 17 / Week 3)
1. Fetch full article text as evidence (richer context)
2. LLM caching (avoid re-summarizing same content)
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

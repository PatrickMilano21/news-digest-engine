# Project Status — News Digest Engine

## Current Day
**Week 4** — 2026-01-28

## Branch
`agent/milestone1` (Milestone 1 + 2 complete, ready for commit)

---

## Milestone 1 — UI & HTML Hardening: COMMITTED

All 9 deliverables shipped and committed.

---

## Milestone 2 — Cost Guardrail + On-Call Debugging: COMPLETE

All 5 deliverables shipped. 228 tests passing.

### Deliverables

| # | Deliverable | Status |
|---|-------------|--------|
| 1 | DATE-scoped daily spend cap at `llm_openai.py` boundary | Done |
| 2 | Mid-run LLM calls refuse with `COST_BUDGET_EXCEEDED` | Done |
| 3 | Run completes with partial summaries | Done |
| 4 | Customer UI shows "Summary skipped — daily processing limit reached" | Done |
| 5 | Debug endpoint `/debug/costs` shows spend, cap, remaining, refusal counts | Done |

### Design Decisions

| Decision | Implementation |
|----------|----------------|
| Spend tracking | Aggregate from `runs.llm_total_cost_usd` via `get_daily_spend()` |
| Cap configuration | Env var `LLM_DAILY_CAP_USD` (default $1.00) |
| Check location | `llm_openai.py` before API call (optional `day` param) |
| Refusal code | `COST_BUDGET_EXCEEDED` in `error_codes.py` |
| Customer message | "Summary skipped — daily processing limit reached" |
| Per-user caps | Deferred to Milestone 4 |

### Files Created
- `tests/test_cost_cap.py` — 10 tests for cost cap functionality

### Files Modified
- `src/repo.py` — added `get_daily_spend()`, `get_daily_refusal_counts()`
- `src/clients/llm_openai.py` — added cap check, `LLM_DAILY_CAP_USD` env var
- `src/error_codes.py` — added `COST_BUDGET_EXCEEDED`
- `src/ui_constants.py` — added `REFUSAL_COST_EXCEEDED` message
- `src/main.py` — added `/debug/costs` endpoint
- `src/artifacts.py` — handle `COST_BUDGET_EXCEEDED` refusal
- `templates/date.html` — show appropriate refusal message

### Tests
- `make test` → 228 passed

---

## Next Up
**Milestone 3 — Feedback → Controlled Weight Updates (Learning Loop)**

Deliverables:
- Aggregate feedback by source
- Compute bounded adjustments (±0.1) with weight bounds (0.5–2.0)
- Persist weight snapshot per cycle
- Run before/after eval comparison artifact
- No regression in grounding/refusal rates

---

## CODEX Commentary

Milestone 2 is marked complete; I have not verified the code or tests yet.
Before merging:
- Confirm new files are tracked and committed (e.g., `tests/test_cost_cap.py`).
- Verify `LLM_DAILY_CAP_USD` default and daily spend query logic are correct.
- Ensure `/debug/costs` is wired and returns spend/cap/remaining/refusals as claimed.
- Run `make test` on this branch to confirm 228 passing.

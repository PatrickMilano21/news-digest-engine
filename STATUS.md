# Project Status — News Digest Engine

**Week 4** — 2026-02-02
**Branch:** `agent/milestone1` → merges to `main`

---

## Milestone Status

| Milestone | Description | Status | Verified |
|-----------|-------------|--------|----------|
| 1 | UI & HTML Hardening | COMPLETE | `make test` (313 passed) |
| 2 | Cost Guardrail + On-Call Debugging | COMPLETE | `make test` + `/debug/costs` |
| 3a | Feedback Reasons (LLM-Suggested, User-Selected) | COMPLETE | `make test` |
| 3b | Controlled Weight Updates (Learning Loop) | COMPLETE | `make test` |
| 3c | TF-IDF AI Score (Content Similarity Boost) | COMPLETE | `make test` |
| 4 | Multi-User Auth + Sessions + Isolation | COMPLETE | `make test` |
| — | Review Agents (5 self-learning) | COMPLETE | `artifacts/agent-findings.md` |
| — | Overnight Automation (7-step workflow) | COMPLETE | `scripts/overnight_local.bat` |
| **4.5** | **AI Configuration Advisor Agent** | **IN PROGRESS** | See Active Task |

---

## Current State

- **Branch workflow:** `agent/milestone1` → `main`
- **Tests:** 397 passed, 17 skipped (`make test` — after Step 5 implementation)
- **Design docs:** AGENT_DESIGN.md + MEMORY_DESIGN.md (implementation-ready)

---

## Build Sequence (Milestone 4.5)

| Step | Component | Status | Rationale |
|------|-----------|--------|-----------|
| **0** | Config-ranking integration | **✅ COMPLETE** | Suggestions now affect ranking |
| **1** | DB schema + repo helpers | **✅ COMPLETE** | 3 tables, 12 repo functions, 18 tests |
| **2** | Advisor tools + validation | **✅ COMPLETE** | 5 tools, 23 tests |
| **2b** | Schema refinement: target_key | **✅ COMPLETE** | target_key + 10-day cooldown |
| **3** | API endpoints | **✅ COMPLETE** | 5 endpoints, 28 tests |
| **4** | UI surface | **✅ COMPLETE** | Manual tested (11 checks) + UI tests |
| 5 | Agent runtime | PENDING | LLM variability last |
| 6 | Tests + evals | PENDING | Verification |

---

## Completed: Step 2b — Schema Refinement (target_key)

**Status:** ✅ COMPLETE
**Completed:** 2026-02-02

### Summary

Added `target_key` column for unambiguous source storage and 10-day cooldown validation.

| File | Changes |
|------|---------|
| `src/db.py` | Added target_key column + idempotent migration |
| `src/repo.py` | Added target_key param, is_target_on_cooldown() |
| `src/advisor_tools.py` | Added target_key + cooldown validation |
| `tests/test_suggestions_repo.py` | 3 new tests |
| `tests/test_advisor_tools.py` | 2 updated/new tests |

**Tests:** 363 passed, 17 skipped

---

## Completed: Step 3 — API Endpoints

**Status:** ✅ COMPLETE
**Completed:** 2026-02-02

### Summary

Added 5 API endpoints for suggestion generation, retrieval, and resolution + increment_profile_stats() helper.

| File | Changes |
|------|---------|
| `src/main.py` | 5 endpoints: /generate, /suggestions, /{id}/accept, /{id}/reject, /accept-all |
| `src/repo.py` | Added increment_profile_stats() helper |
| `tests/test_suggestions_api.py` | 28 integration tests |

**Tests (at Step 3 completion):** 391 passed, 17 skipped

### Verified

- [x] All 5 endpoints implemented in src/main.py
- [x] Auth required on all endpoints
- [x] 409 returned on double-accept/reject
- [x] Accept updates config + stores outcome
- [x] Reject stores outcome only
- [x] Config mutations handle edge cases (duplicate topics, missing topics, numeric weights)
- [x] increment_profile_stats() helper implemented
- [x] User isolation enforced
- [x] Integration tests pass

---

## Completed: Step 4 — UI Surface

**Status:** ✅ COMPLETE
**Completed:** 2026-02-04

### Goal

Add UI for viewing and resolving suggestions with user-friendly presentation.

### UX Decisions (Locked)

| Decision | Choice |
|----------|--------|
| JS approach | Vanilla JS (matches date.html patterns) |
| Rendering | Server-render on page load, JS for actions only |
| Nav placement | "Suggestions" after "Config" |
| Nav badge | Skip for v1 |
| Weights display | Hidden by default, friendly language |
| Accept control | Individual + "Accept All" |
| After action | Card → "✓ Applied" / "✗ Dismissed", fade out |
| Evidence | Badge only ("Based on 5 articles") |
| Grouping | Sources section, Topics section |
| Empty state | Explanation + "Generate Suggestions" CTA |
| Generate flow | Inline status messages, no modals |
| Step 5 not wired | Generate shows "Coming soon" message |

### Sub-steps

| Step | Description | Files |
|------|-------------|-------|
| **4.1** | Route + basic template | `main.py`, `suggestions.html` |
| **4.2** | Suggestion cards + grouping | `suggestions.html` |
| **4.3** | JavaScript actions | `suggestions.html` |
| **4.4** | Feedback states | `suggestions.html` |
| **4.5** | Nav link | `_base.html` |

---

### Step 4.1 — Route + Basic Template

```
GET /ui/suggestions (auth required)
  → Fetch pending suggestions via internal call
  → If none: show empty state + Generate button
  → If some: render cards grouped by type
```

**Empty state:**
```
┌─────────────────────────────────────────────────────┐
│        💡                                           │
│   No suggestions yet                                │
│                                                     │
│   We'll analyze your recent feedback to suggest     │
│   improvements to your news digest.                 │
│                                                     │
│              [Generate Suggestions]                 │
└─────────────────────────────────────────────────────┘
```

---

### Step 4.2 — Suggestion Cards

**Card anatomy:**
```
┌─────────────────────────────────────────────────────┐
│ 📈 Show me more from Reuters          Small boost   │
│                                                     │
│ You liked 8/10 Reuters articles last week.          │
│                                                     │
│ Based on 5 articles                                 │
│                                                     │
│ [Details ▼]                   [Reject]  [Accept ✓]  │
└─────────────────────────────────────────────────────┘
```

**Details toggle:**
- **Sources:** Show `Current: 1.0 → Proposed: 1.3` (numeric values)
- **Topics:** Show "This will add/remove the topic from your interests"

**Type mapping:**

| Type | Icon | Headline | Value source |
|------|------|----------|--------------|
| `boost_source` | 📈 | "Show me more from {target_key}" | `target_key` |
| `reduce_source` | 📉 | "Show me less from {target_key}" | `target_key` |
| `add_topic` | ➕ | "Add '{suggested_value}' to your interests" | `suggested_value` |
| `remove_topic` | ➖ | "Remove '{suggested_value}' from your interests" | `suggested_value` |

**Note:** Don't use `field` in UI — it's always "source_weights" or "topics".

**Boost level (source suggestions only):**

| Delta | Label |
|-------|-------|
| ≤ 0.15 | Small boost/reduction |
| 0.16–0.25 | Moderate boost/reduction |
| > 0.25 | Big boost/reduction |

**Safe math:** Only compute boost level if both `current_value` and `suggested_value` are numeric. Otherwise, hide the label and show only the headline.

**Grouping:** Sources section, then Topics section.

---

### Step 4.3 — JavaScript Actions

| Button | Endpoint | On Success |
|--------|----------|------------|
| Generate | `POST /api/suggestions/generate` | Render cards or show status message |
| Accept | `POST /api/suggestions/{id}/accept` | Card → "✓ Applied" |
| Reject | `POST /api/suggestions/{id}/reject` | Card → "✗ Dismissed" |
| Accept All | `POST /api/suggestions/accept-all` | Per-card: accepted/rejected/failed |

---

### Step 4.4 — Feedback States

**Action states:**

| State | UI |
|-------|-----|
| Generating | Button disabled, "Generating..." |
| Card accepted | "✓ Applied" (fade out after 2s) |
| Card rejected | "✗ Dismissed" (fade out after 2s) |
| All done | "All done! Your preferences have been updated." |

**Generate responses:**

| API Status | UI |
|------------|-----|
| `ready` | "Coming soon — agent not yet enabled" (Step 5 pending) |
| `completed` | Render new suggestion cards (future, when Step 5 wired) |
| `blocked_pending` | Re-render existing suggestions |
| `already_generated` | Re-render existing suggestions |
| `skipped` | "Not enough feedback yet. Keep rating articles and check back later." |

**Error codes → User messages:**

| API Error | User Message |
|-----------|--------------|
| `already_resolved` | "Already handled" |
| `invalid_weight` | "Couldn't apply this change" |
| `missing_target_key` | "This suggestion is no longer valid" |
| `not_found` (404) | "Suggestion not found" |
| Other errors | "Something went wrong. Please try again." |

**Accept-all partial results:** Use per-item `results[]` to mark each card as accepted, rejected, or failed individually.

---

### Step 4.5 — Nav Link

Add to `_base.html` after Config:
```html
<a href="/ui/suggestions" class="nav-link">💡 Suggestions</a>
```

---

### Definition of Done

- [x] `/ui/suggestions` renders with auth required (server-rendered)
- [x] Empty state shows Generate button + explanation
- [x] Cards display with friendly language (target_key for sources, suggested_value for topics)
- [x] Boost level labels only shown when both values are numeric
- [x] Details toggle: numbers for sources, text for topics
- [x] Accept/Reject work individually with correct error messages
- [x] Accept All works with per-item result handling
- [x] Generate handles `ready` → "Coming soon" (Step 5 not wired)
- [x] Generate handles: blocked_pending, already_generated, skipped
- [x] Cards fade out after action
- [x] "All done" message when no cards left
- [x] Nav link added after Config
- [x] Manual testing passes (2026-02-04)

---

## Active Task: Step 5 — Agent Runtime

**Status:** PLANNING
**Depends on:** Step 4 (✅ complete)

### Goal

Wire the OpenAI tool-calling agent that analyzes user feedback and generates config suggestions. This is the "brain" that makes Generate Suggestions actually work.

### Architecture

```
POST /api/suggestions/generate
    → src/advisor.py:run_advisor(user_id, conn)
        → Load prompt from .claude/agents/config-advisor.md
        → OpenAI chat completions (gpt-4o) with function calling
        → Loop: dispatch tool calls → advisor_tools.py → repo.py
        → Insert suggestions into DB
    → Return {status: 'completed', suggestion_ids: [...]}
```

### Sub-steps

| Step | Description | Files | Blocked By |
|------|-------------|-------|------------|
| **5.1** | Agent prompt file | `.claude/agents/config-advisor.md` | — |
| **5.2** | Advisor runtime (orchestration + tool-calling loop) | `src/advisor.py` | 5.1 |
| **5.3** | Wire generate endpoint to advisor | `src/main.py` | 5.2 |
| **5.4** | Scheduled job for weekly runs | `jobs/run_advisor.py` | 5.2 |
| **5.5** | Update LLM_DAILY_CAP_USD to $5.00 (ingest) | `src/clients/llm_openai.py` | — |
| **5.6** | Update UI for 'completed' + error states | `templates/suggestions.html` | 5.3 |
| **5.7** | Smoke test end-to-end | Manual | 5.3, 5.6 |

### Key Design Decisions

| Decision | Choice |
|----------|--------|
| Model | gpt-4o (hardcoded in advisor.py) |
| HTTP client | `openai` Python library — add to `pyproject.toml` with pinned version (e.g., `openai>=1.0,<2.0`) |
| Budget cap | $1.00/day for advisor (`ADVISOR_DAILY_CAP_USD` env var) |
| Ingest cap | $5.00/day (update `LLM_DAILY_CAP_USD` default from $1.00) |
| Tool dispatch | `_handle_tool_call(name, args, conn)` → advisor_tools.py functions |
| Cost tracking | `start_run(run_type='advisor')` → `update_run_llm_stats()` → `finish_run_ok()` |
| Prompt loading | Read .md file, explicit YAML frontmatter parser (split on `---` markers) |

### Guardrails (Three Separate Caps)

| Guardrail | Value | Enforced In | Purpose |
|-----------|-------|-------------|---------|
| Max API turns | 50 | `advisor.py` loop counter | Hard safety net — prevents runaway API calls |
| History window | 15 turns | `advisor.py` message trimming | Token efficiency — agent doesn't need full history |
| Max tool calls | 30 | `advisor.py` tool call counter | Prevents tool-call loops (separate from API turns) |

All three enforced independently. If any cap is hit → exit with `agent_error` status + structured log.

**Budget check frequency:**
- Check `get_daily_spend_by_type(run_type='advisor')` **before each OpenAI API call**, not just at start
- In-memory accumulator tracks cost for the current run (used only for "should we call again?" decision)
- DB total (`get_daily_spend_by_type`) is the source of truth for cross-run daily totals — in-memory accumulator is added to the DB total for comparison, never written to DB until `update_run_llm_stats()` is called (no double-counting)
- If mid-loop budget exceeded → exit cleanly with partial results (see below)

### Step 5.4 — Scheduled Job Decisions (Locked)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Weekly check | `runs` table (`run_type='advisor'` + `user_id` + last 7 days) | Canonical source, aligns with cost tracking |
| `--all-users` | Pre-filter with sufficiency check before calling agent | Saves OpenAI API cost for users without enough data |
| Override | `--force` flag skips 7-day check (still blocked by 1/day limit) | User can force a re-run, but never more than once per day |
| Trigger | Manual CLI for now (no Task Scheduler yet) | `python -m jobs.run_advisor --all-users` or `--user-id X` |
| Run limit | 1 run/user/day enforced even with `--force` | Checked via `already_generated` (suggestions created today), NOT via cost cap |

**Enforcement consistency (two separate concerns):**
- **Run limit (1/day):** Checked via `already_generated` — any suggestions created today for this user blocks a re-run. Enforced in both `/api/suggestions/generate` and inside `run_advisor()` (concurrency guard).
- **Cost cap ($1/day):** Checked via `get_daily_spend_by_type(conn, day, run_type='advisor')` — prevents budget overrun. Enforced per API call inside `run_advisor()`.
- `jobs/run_advisor.py` with `--force` skips 7-day window but `run_advisor()` still checks both run limit and cost cap
- All three layers work together: job → endpoint → runtime

**Concurrency guard (UI + nightly overlap):**
- `run_advisor()` re-checks `already_generated` (suggestions created today) right before first `write_suggestion` call
- Prevents: UI clicks Generate at same time nightly job runs → double suggestions
- If already generated → return early with `already_generated` status, no duplicate writes

**CLI interface:**
```
python -m jobs.run_advisor --user-id UUID          # Single user, respects 7-day window
python -m jobs.run_advisor --user-id UUID --force   # Single user, skip 7-day (still 1/day)
python -m jobs.run_advisor --all-users              # All users, pre-filter + 7-day window
python -m jobs.run_advisor --all-users --force       # All users, pre-filter + skip 7-day
```

---

### Step 5.7 — Smoke Test Decisions (Locked)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Test method | Manual smoke test | MCP extension is non-trivial, would slow shipping |
| Feedback thresholds | Temporarily lower for smoke test (same as Step 4) | Seeding 7 days of real data is too much work for a smoke test |
| Documentation | Add to `ManualTesting.md` as new section | Reusable for future runs |
| MCP automation | Future work (logged in `future.md`) | Automate once flow is stable |

---

### Step 5.6 — UI Generate Handler Decisions (Locked)

| Status | UI Action |
|--------|-----------|
| `completed` | Reload page to show new cards |
| `budget_exceeded` | If `suggestions_created > 0`: reload page (partial results). Otherwise: "Daily suggestion limit reached. Try again tomorrow." |
| `agent_timeout` | If `suggestions_created > 0`: reload page (partial results). Otherwise: "Suggestion generation took too long. Please try again." |
| `agent_error` | If `suggestions_created > 0`: reload page (partial results). Otherwise: "Something went wrong generating suggestions. Please try again." |
| `ready` | Keep as safety fallback — "Coming soon — agent not yet enabled" |

**Partial results UI rule:** All error statuses (`budget_exceeded`, `agent_timeout`, `agent_error`) include `suggestions_created` count in the response. If > 0, reload the page so the user sees the cards that were created. Error message only shown when zero suggestions were written.

**When `ready` triggers (fallback scenarios):**
- `OPENAI_API_KEY` env var not set → agent can't run, endpoint returns `ready`
- Agent feature flag disabled (future) → same behavior
- `advisor.py` import fails → endpoint catches, returns `ready`

---

### Step 5.5 — Budget Cap Decisions (Locked)

| Decision | Choice |
|----------|--------|
| `LLM_DAILY_CAP_USD` | Default $5.00 (ingest spend) — one-line change in `llm_openai.py` |
| `ADVISOR_DAILY_CAP_USD` | Default $1.00 (advisor spend) — new env var in `advisor.py` |
| Isolation | Each cap checked via `get_daily_spend_by_type(conn, day, run_type)` |
| Pre-build check | Verify no `.env` override masks the code change |

---

### Step 5.3 — Generate Endpoint Decisions (Locked)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Execution model | Sync (blocking) for v1 | Simple, predictable. Move to async if latency becomes UX issue |
| Server timeout | 30s hard cap on `run_advisor()` | Surface `agent_timeout` status if hit |
| Partial output | Acceptable — suggestions already written to DB are kept | Timeout/budget/error mid-loop = partial results, not rollback |
| HTTP status | 200 + status field for all expected outcomes | Consistent with existing `skipped`, `blocked_pending`, `already_generated` |
| 500 only for | Truly unexpected failures (uncaught exceptions) | Not for known agent outcomes |

**Partial output policy:**
- `write_suggestion()` commits each suggestion individually (no wrapping transaction)
- If agent writes 2 suggestions then times out → user sees those 2 suggestions
- Status returned: `agent_timeout` with `suggestions_created: 2` (partial count)
- Same for budget exceeded mid-loop: keep what was written, report partial

**Generate endpoint status responses (complete set):**

| Status | Meaning | When |
|--------|---------|------|
| `blocked_pending` | Existing suggestions need resolution | Pending suggestions exist |
| `already_generated` | Already ran today | Suggestions created today (any status) |
| `skipped` | Not enough feedback data | Data sufficiency check fails |
| `completed` | Agent ran successfully | New suggestions created |
| `budget_exceeded` | Daily advisor cap hit | `ADVISOR_DAILY_CAP_USD` exceeded |
| `agent_timeout` | Agent took too long | 30s timeout hit |
| `agent_error` | Agent failed (tool error, API error) | Known failure during agent run |

---

### Step 5.2 — Advisor Runtime Decisions (Locked)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| OpenAI client | `openai` Python library (add dependency) | Function calling loop is much cleaner, less error-prone, future-proof |
| Message history | Capped at 15 turns max | Agent doesn't need full loop history; tools return structured outputs |
| Error recovery | Return errors to agent, retry allowed | But: same tool + same error twice → stop and log (no infinite loops) |
| Max API turns | 50 hard cap (defense-in-depth) | Safety net — loop counter on API round-trips |
| Max tool calls | 30 hard cap | Separate from turns — prevents tool-call spam within a single turn |

**History management strategy (turn-based, NOT token-based):**
- Cap is 15 **turns** (assistant message + tool response = 1 turn)
- Keep system message + user context message + last 15 turns
- If history exceeds 15 turns, trim oldest turns (system + user context always kept)
- Agent tools return structured JSON — context is self-contained per call
- v2 consideration: add token-based trimming if tool responses are unexpectedly large

**Error retry guardrail:**
- Track `{tool_name, error_code}` pairs per run
- If same pair seen twice → skip that hypothesis, move on
- If retry guard trips → exit loop cleanly with `agent_error` status + structured log
- Prevents: agent calling `write_suggestion` in a loop with the same bad evidence
- Generate endpoint receives `agent_error` and returns 200 + status to UI (never hangs)

---

### Step 5.1 — Agent Prompt Decisions (Locked)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Reasoning steps | Prescriptive 6-step loop in prompt | Reliable tool order + guardrails |
| Examples | One `write_suggestion` example | Sharply improves correctness, worth token cost |
| user_id injection | Separate system message (not in prompt file) | Prompt file stays static, user_id is dynamic context |
| Prompt file | `.claude/agents/config-advisor.md` with YAML frontmatter (docs only) | Version controlled, runtime strips frontmatter |
| Frontmatter parser | Explicit: split on `---` markers, validate exactly 2 markers exist | No blind stripping — fail clearly if format is wrong |
| Missing prompt file | `load_agent_prompt()` returns None → `run_advisor()` returns `agent_error` | Never crash the endpoint — log clearly, return 200 + status |
| YAML parse failure | Same as missing file — `agent_error` with descriptive log | Endpoint stays up, user sees error message |

**Prompt structure:**
1. YAML frontmatter (documentation only — name, description, model)
2. Persona (senior engineer internally, friendly expert externally)
3. Scope (topics + source weights only, no recency in v1)
4. 6 prescriptive steps: Explore → Analyze → Hypothesize → Validate/Write → Critique → Output
5. Tool descriptions (what each tool does, when to call it)
6. Constraints (max 3 suggestions, min 3 evidence, confidence levels)
7. One concrete `write_suggestion` example
8. Output format (JSON summary for logging)

### Suggestion Caps (Stability)

| Cap | Value | Rationale |
|-----|-------|-----------|
| Max suggestions per run | 3 | Quality over quantity, reduce overwhelm |
| Max source changes per run | 1 | Avoid drastic ranking shifts |
| Max topic changes per run | 1 | Focused recommendations |
| Third slot | Either source or topic | Flexibility if one category has no suggestions |

### Cooldown Policy (10 days)

| Rule | Value |
|------|-------|
| Cooldown period | 10 days |
| Scope | Per target_key (source or topic name) |
| Applies to | Both accepted AND rejected suggestions |
| Behavior | Don't generate (reject in write_suggestion), not create-and-hide |

### What Already Exists

| Component | Status | Location |
|-----------|--------|----------|
| OpenAI client pattern | ✅ | `src/clients/llm_openai.py` |
| 5 advisor tools | ✅ | `src/advisor_tools.py` |
| DB schema (3 tables) | ✅ | `src/db.py` |
| Repo CRUD (12 functions) | ✅ | `src/repo.py` |
| API endpoints (5 routes) | ✅ | `src/main.py` |
| UI surface | ✅ | `templates/suggestions.html` |
| Cost tracking pattern | ✅ | `src/repo.py` (start_run, update_run_llm_stats) |

### What Needs to Be Built

| Component | Description |
|-----------|-------------|
| `.claude/agents/config-advisor.md` | Full agent prompt with persona + reasoning loop |
| `src/advisor.py` | OpenAI orchestration: load prompt, define tool schemas, run loop, track cost |
| `jobs/run_advisor.py` | CLI for scheduled runs (--user-id, --all-users) |
| Wire generate endpoint | Replace 'ready' placeholder with `run_advisor()` call |
| Update UI JS | Handle 'completed', 'budget_exceeded', 'agent_error' statuses + partial results reload |
| Update budget default | `LLM_DAILY_CAP_USD` from $1.00 → $5.00 |
| Add `openai` dependency | Pin in `pyproject.toml` (e.g., `openai>=1.0,<2.0`) |

### Definition of Done

- [x] Agent prompt written and version-controlled
- [x] `run_advisor()` completes a full tool-calling loop
- [x] Generate endpoint calls advisor and returns suggestions
- [x] Cost tracked in runs table with `run_type='advisor'`
- [x] Budget cap enforced ($1.00/day for advisor, $5.00/day for ingest)
- [x] Scheduled job works (`jobs/run_advisor.py`)
- [x] UI handles 'completed' status (reload shows cards)
- [x] UI handles error states (budget_exceeded, agent_error, agent_timeout) + partial results
- [ ] End-to-end smoke test passes
- [x] `make test` passes (397 passed, 17 skipped)

---

## Key Decisions (Locked)

| Decision | Choice |
|----------|--------|
| Provider | OpenAI API (gpt-4o) |
| Architecture | advisor.py → advisor_tools.py → repo.py |
| Agent location | `.claude/agents/config-advisor.md` |
| Invocation | User-triggered (UI) + scheduled (every 7 days) |
| Memory | DB tables + `.claude/rules/config-advisor/` patterns |
| v1 Scope | Topics + sources only (recency deferred to v2) |
| Cost tracking | Reuse `runs` table with `run_type='advisor'` |
| Budget caps | Summaries $5/day (`run_type='ingest'`), Advisor $1/day (`run_type='advisor'`) |
| ⚠️ Code default | `LLM_DAILY_CAP_USD` in `llm_openai.py` is $1.00 — update to $5.00 during implementation |

---

## Reference

| Document | Purpose |
|----------|---------|
| [AGENT_DESIGN.md](AGENT_DESIGN.md) | Architecture, tools, reasoning loop, guardrails |
| [MEMORY_DESIGN.md](MEMORY_DESIGN.md) | Memory architecture, 3-layer retrieval, profiles |
| [completion.md](completion.md) | What's done (chronological log) |
| `week4.md` | Weekly accomplishments |
| `future.md` | Backlog items |

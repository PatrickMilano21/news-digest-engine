# Config Advisor Agent — Design Document

Designing a top-tier, senior-engineer-level agent for config recommendations.

**Related Documents:**
- [MEMORY_DESIGN.md](MEMORY_DESIGN.md) — Memory architecture, 3-layer retrieval, user profiles
- [AI_CAPABILITIES.md](AI_CAPABILITIES.md) — Skills, hooks, MCPs, eval patterns
- [STATUS.md](STATUS.md) — Data model, API endpoints, acceptance criteria

---

## Why an Agent (Not Just a Job)

The Config Advisor should be a full agent because:

1. **Exploratory reasoning** — needs to discover patterns, not just execute steps
2. **Iterative refinement** — generate → critique → improve cycle
3. **Judgment calls** — deciding *what* to suggest requires reasoning
4. **Expandable** — agent architecture supports growing capabilities
5. **Learning** — can adapt based on what users accept/reject

---

## BLOCKING Pre-Work: Config-Ranking Integration

**Status:** Must complete before building agent

**Problem:** `get_effective_rank_config()` exists in `views.py` but ranking code in `daily_run.py`, `build_digest.py`, and `main.py` uses `RankConfig(source_weights=...)` directly.

**Impact:** If not fixed, accepted suggestions will update `user_configs` but **ranking won't change**. The agent would be useless.

**Fix:** Consolidate to one config path everywhere ranking occurs:
```python
# BEFORE (scattered in multiple files):
cfg = RankConfig(source_weights=source_weights)

# AFTER (use helper that merges user_configs + active weights):
cfg = get_effective_rank_config(conn, user_id=user_id)
```

**Files to update:**
- `jobs/daily_run.py` — ranking call
- `jobs/build_digest.py` — ranking call
- `src/main.py` — API ranking calls

**Why this is Step 0:** Without this fix, the entire agent is pointless. Config changes must flow through to ranking.

---

## Execution Model

### Stateless Design
The agent does not maintain state between runs. Each invocation:
- Receives `user_id` as input parameter
- Queries fresh data from DB (feedback, config, history)
- Produces suggestions scoped to that user
- Writes to user-scoped tables (`config_suggestions.user_id`)

### Concurrent Users
Multiple users can invoke the agent simultaneously with no conflict:
```
User A calls agent ──→ queries A's feedback ──→ writes to A's suggestions
User B calls agent ──→ queries B's feedback ──→ writes to B's suggestions
         (parallel execution, isolated data)
```

### User Isolation
All tools receive `user_id` and scope queries accordingly:
- `query_user_feedback(user_id, ...)` — only this user's feedback
- `query_user_config(user_id)` — only this user's config
- `write_suggestion(user_id, ...)` — tagged to this user

No cross-user data leakage possible by design.

### Single Agent (v1)
The agent prompt contains persona, reasoning loop, and output contract in one file. No sub-agents.

**Why not sub-agents?**
- Adds latency (multiple API calls)
- Adds complexity (coordination)
- Single agent can handle the reasoning loop via multi-turn tool use

**v2 consideration:** If the agent struggles with complex reasoning, could split into data-gatherer → hypothesis-generator → critic pipeline.

---

## Provider: OpenAI API

**Decision:** Use **OpenAI API** for the config advisor agent.

**Status:** FINAL

**Rationale:**

1. **User-triggered requests require API call** — Can't shell out to Claude CLI from a web handler
2. **Existing infrastructure** — Already have OpenAI client in `src/clients/llm_openai.py`
3. **Cost tracking in place** — Reuse existing patterns with `run_type='advisor'`
4. **Function calling works** — OpenAI supports tool use, sufficient for our needs
5. **Lower risk** — No new API client, no new credentials, no new cost model

**Architecture:** See "Tool implementation?" section below for the 3-layer design (advisor.py → advisor_tools.py → repo.py).

---

## Basic Agent vs Top-Tier Agent

| Dimension | Current Review Agents | Top-Tier Config Advisor Agent |
|-----------|----------------------|-------------------------------|
| **Goal** | "Scan for X patterns" | "Figure out what would improve this user's digest" |
| **Approach** | Single pass, pattern match | Iterative: explore → hypothesize → validate → refine |
| **Tools** | Read, Grep, Write | Rich toolset: query DB, compute stats, test hypotheses |
| **Reasoning** | Implicit | Explicit chain-of-thought, documented |
| **Uncertainty** | Flag everything | Confidence levels, "unsure because X" |
| **Self-critique** | None | Reviews own suggestions before presenting |
| **Memory** | Static learned-patterns.md | Dynamic: tracks what worked, adapts |

---

## Key Architectural Differences

### 1. Goal-Oriented, Not Task-Oriented

**Basic agent prompt:**
```
Scan repo.py for missing user_id parameters. Write findings.
```

**Top-tier agent prompt:**
```
You are a senior engineer helping optimize this user's news digest experience.
Analyze their feedback patterns, understand their preferences, and recommend
config changes that would improve relevance. Justify each recommendation with
evidence. Only suggest changes you're confident will help.
```

### 2. Rich Tool Environment

The agent needs tools to *think*, not just scan:

| Tool | Purpose |
|------|---------|
| `query_user_feedback` | Get liked/disliked items with patterns pre-computed |
| `query_user_config` | Get current config + active weights |
| `get_user_profile` | Acceptance history, learned patterns, trends |
| `write_suggestion` | Validate and store suggestion (validation built-in) |
| `get_suggestion_outcomes` | 3-layer memory retrieval (search → timeline → detail) |

**Phase 2 additions:**
| `test_suggestion` | "If I add this topic, how many past items would match?" |
| `self_critique` | "Review my suggestions for issues" |

### 3. Reasoning Loop (Not Single Pass)

```
1. EXPLORE: What does this user's feedback tell me?
2. HYPOTHESIZE: What changes might help?
3. TEST: Would this change have improved past digests? (Phase 2)
4. WRITE: Call write_suggestion — validation happens server-side
5. CRITIQUE: If rejected, why? Adjust evidence and retry
6. REFINE: Improve weak suggestions based on feedback
7. PRESENT: Output with confidence + reasoning
```

### 4. Self-Critique Built In

Before outputting, agent asks itself:
- "Is this suggestion grounded in evidence?"
- "Could this be a hallucination?"
- "Would a user understand why I'm suggesting this?"
- "What's my confidence level?"

### 5. Memory Across Runs

```
Last run: Suggested "add topic: Kubernetes" → USER ACCEPTED
Last run: Suggested "reduce source: theverge" → USER REJECTED
Learning: User is open to topic additions but protective of sources
```

---

## Agent Tool Set

### Core Tools (Phase 1)

| Tool | Input | Output | Purpose |
|------|-------|--------|---------|
| `query_user_feedback` | user_id | Curated items + patterns | Understand preferences (includes source_patterns, tag_patterns) |
| `query_user_config` | user_id | Merged config view | Know starting point (config + active weights) |
| `get_user_profile` | user_id | Acceptance stats, patterns | Learn from past outcomes |
| `write_suggestion` | suggestion_data | suggestion_id or error | Validate + store suggestion (server-side validation) |
| `get_suggestion_outcomes` | user_id, layer, query | Varies by layer | 3-layer memory retrieval (search → timeline → detail) |

**Note:** `compute_source_stats` and `compute_topic_frequency` were removed — their functionality is now included in `query_user_feedback` (pre-computed patterns returned with curated items).

### Advanced Tools (Phase 2)

| Tool | Input | Output | Purpose |
|------|-------|--------|---------|
| `test_suggestion` | suggestion, historical_items | {would_match: N, examples[]} | Backtest suggestion |
| `self_critique` | suggestions[] | {issues[], confidence[]} | Review own work |
| `get_acceptance_history` | user_id | {accepted[], rejected[]} | Learn from past |
| `compare_configs` | config_before, config_after | {diffs[], impact_estimate} | Understand changes |

---

## Reasoning Framework

### Agent Persona

**Dual persona design:**
| Layer | Mindset | Purpose |
|-------|---------|---------|
| Internal reasoning | Senior engineer | Rigorous, evidence-based, self-critical |
| External output | Friendly expert | Clear, confident, semi-technical |

**Tone:** Confident (not hedging)
- YES: "Adding Kubernetes as a topic will surface more container content you've enjoyed"
- NO: "You might want to consider possibly adding Kubernetes"

**Scope (v1):** Explicit boundaries
```
You can suggest changes to:
- Topics (add/remove keywords)
- Source weights (boost/reduce specific sources)

You cannot suggest changes to (out of scope for v1):
- Recency settings
- Delivery preferences
- UI preferences
```

**User model:** Semi-technical
- Users understand "source weight" and "topic matching"
- Avoid implementation details (scores, algorithms)
- Example: "Articles from Ars Technica will rank higher" (not "boost weight from 1.0 to 1.3")

**Full prompt (draft):**
```markdown
You are a personalization expert helping optimize this user's news digest.
Analyze their feedback patterns and recommend configuration changes that
would improve relevance.

Think like a senior engineer: require evidence, validate assumptions,
self-critique before outputting. But communicate like a helpful expert:
clear, confident, no jargon.

You can suggest changes to:
- Topics (add/remove keywords that match article content)
- Source weights (boost/reduce how much a source influences ranking)

Guidelines:
- Only suggest changes you're confident will help
- Every suggestion must cite specific items as evidence
- Quality over quantity — 2 good suggestions beat 5 mediocre ones
- Express confidence level (high/medium) for each suggestion
- If data is insufficient, say so rather than guessing
```

### Reasoning Steps

```markdown
## Step 1: Explore
Use query_user_feedback to get recent liked/disliked items.
Look for patterns: What sources do they like? What topics appear frequently?

## Step 2: Analyze
Use patterns returned by `query_user_feedback` (source_patterns, tag_patterns).
Derive topic candidates from curated item titles (e.g., "3 of 5 liked items mention Kubernetes").
Identify: High like-rate sources, common themes in liked item titles, patterns in disliked items.

## Step 3: Hypothesize
Based on patterns, form hypotheses:
- "User likes Kubernetes content → add 'Kubernetes' topic"
- "User dislikes theverge (20% like rate) → reduce source weight"

## Step 4: Validate + Write
Call write_suggestion for each hypothesis.
Built-in validation ensures evidence is real, rejects ungrounded suggestions.
Agent receives success/failure for each — can retry with better evidence if needed.

## Step 5: Critique
For each validated suggestion, ask:
- Could this backfire?
- Is the evidence strong enough?
- Would the user understand this suggestion?

## Step 6: Output
Present suggestions with:
- What to change
- Why (evidence)
- Confidence level (high/medium/low)
- Expected impact
```

---

## Detailed Reasoning Loop

### Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  START: Agent receives user_id                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: CHECK DATA SUFFICIENCY                                 │
│                                                                  │
│  Tool: query_user_feedback(user_id)                             │
│                                                                  │
│  Decision:                                                       │
│    - If insufficient_data=true → EXIT with "need more feedback" │
│    - Else → Continue to Step 2                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 2: LOAD CONTEXT                                           │
│                                                                  │
│  Tools (parallel):                                               │
│    - query_user_config(user_id)                                 │
│    - get_user_profile(user_id)  ← acceptance history            │
│                                                                  │
│  Agent now knows:                                                │
│    - Current config (topics, weights)                           │
│    - Past acceptance patterns (what they reject/accept)         │
│    - Feedback patterns (from Step 1)                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 3: FORM HYPOTHESES                                        │
│                                                                  │
│  Agent reasoning (internal):                                     │
│    "Based on patterns, I hypothesize:"                          │
│    - User likes techcrunch (85% rate) → consider boost          │
│    - User dislikes hype content → reduce theverge?              │
│    - 'kubernetes' appears in 4/5 liked items → add topic?       │
│                                                                  │
│  Constraints (from profile):                                     │
│    - User never accepts reduce_source → skip source reductions  │
│    - User prefers additions over removals → prioritize adds     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 4: WRITE SUGGESTIONS (with validation)                    │
│                                                                  │
│  For each hypothesis:                                            │
│    Tool: write_suggestion(suggestion_data)                      │
│                                                                  │
│    If success=true:                                              │
│      → Suggestion stored, move to next                          │
│    If success=false:                                             │
│      → Read error, adjust (add evidence, change value)          │
│      → Retry once with better data                              │
│      → If still fails, skip this hypothesis                     │
│                                                                  │
│  Stop when:                                                      │
│    - 1-3 suggestions written successfully                       │
│    - OR all hypotheses exhausted                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 5: OUTPUT SUMMARY                                         │
│                                                                  │
│  Generate JSON output with:                                      │
│    - suggestions[] (what was written)                           │
│    - skipped[] (what was attempted but failed/insufficient)     │
│    - meta{} (stats about the run)                               │
│                                                                  │
│  This output is for logging/debugging.                          │
│  User sees suggestions via GET /api/suggestions                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                           [ END ]
```

### Branching Logic

| Condition | Action |
|-----------|--------|
| `insufficient_data=true` | Exit early, return `{suggestions: [], reason: "..."}` |
| Profile shows `never_reduce_sources=true` | Skip all reduce_source hypotheses |
| Profile shows `open_to_new_topics=true` | Prioritize add_topic hypotheses |
| No clear patterns found | Exit with `{suggestions: [], reason: "feedback is balanced, no clear improvements"}` |
| write_suggestion fails 2x for same hypothesis | Skip that hypothesis, continue |
| 3 suggestions written | Stop (quality cap: max 1 source + 1 topic + 1 flex) |

### Error Handling

| Error | Source | Handling |
|-------|--------|----------|
| Tool timeout | Infrastructure | Retry once, then exit with error |
| Validation failure | write_suggestion | Adjust evidence, retry once |
| Empty feedback | query_user_feedback | Exit early with helpful message |
| Profile not found | get_user_profile | Continue without acceptance history (first run) |

### Success Criteria

A successful run produces:
- 0-3 validated suggestions (0 is okay if data is insufficient/balanced)
- Each suggestion has 3+ evidence items
- No ungrounded suggestions stored
- Clear reasoning for skipped hypotheses
- Run completes in <50 turns

---

## DB Integration & API Endpoints

### Tables Overview

| Table | Purpose | Owner |
|-------|---------|-------|
| `config_suggestions` | Pending/resolved suggestions | Agent writes, API reads |
| `suggestion_outcomes` | Rich snapshots of accept/reject | API writes on user action |
| `user_preference_profiles` | Computed patterns from outcomes | Updated on each outcome |
| `user_configs` | Live user config | Updated on accept |

**Schema:** See STATUS.md for `config_suggestions`, MEMORY_DESIGN.md for full `suggestion_outcomes` and `user_preference_profiles`.

### API Endpoints

#### POST /api/suggestions/generate

Triggers the agent to analyze feedback and create suggestions.

**Check order:**
1. If ANY pending suggestions exist → `blocked_pending` (UX stability)
2. If ANY suggestions created today (any status) → `already_generated` (cost guard)
3. Check data sufficiency → `skipped` or proceed
4. Run agent → `completed`

```
Request:  POST /api/suggestions/generate
Headers:  Cookie: session_id=...  (user_id from session)
Body:     {} (no body needed, user_id from session)

Response (pending exists — must resolve first):
{
  "status": "blocked_pending",
  "pending_count": 2,
  "suggestion_ids": [42, 43]
}

Response (already ran today — idempotent):
{
  "status": "already_generated",
  "suggestion_ids": [42, 43, 44]
}

Response (insufficient data):
{
  "status": "skipped",
  "reason": "Need at least 10 feedback items (you have 4)"
}

Response (success):
{
  "status": "completed",
  "suggestions_created": 3,
  "suggestion_ids": [42, 43, 44]
}
```

**Guardrails:**
- **Pending check:** User must resolve existing suggestions before generating new ones
- **Idempotency:** If suggestions already exist for this user today (any status), return them instead of re-running the agent
- **Cooldown (10 days):** Individual targets can't be re-suggested within 10 days (enforced in `write_suggestion`)
  - Applies to both accepted AND rejected suggestions
  - Scope: per target_key regardless of suggestion_type
- **Suggestion caps:** Max 3 per run (1 source + 1 topic + 1 flex)

**Implementation:** Calls `src/advisor.py` which invokes OpenAI API with agent prompt and function schemas.

#### GET /api/suggestions

Get pending suggestions for current user.

```
Request:  GET /api/suggestions
Headers:  Cookie: session_id=...

Response:
{
  "suggestions": [
    {
      "suggestion_id": 42,
      "suggestion_type": "boost_source",
      "field": "source_weights",
      "target_key": "techcrunch",
      "current_value": "1.0",
      "suggested_value": "1.3",
      "reason": "You liked 8/10 articles from TechCrunch",
      "evidence_count": 8,
      "status": "pending",
      "created_at": "2026-02-01T10:00:00Z"
    }
  ],
  "count": 1
}
```

#### POST /api/suggestions/{id}/accept

Accept a suggestion → updates config + stores outcome.

```
Request:  POST /api/suggestions/42/accept
Headers:  Cookie: session_id=...
Body:     {} (optional: {"user_reason": "sounds good"})

Response:
{
  "success": true,
  "suggestion_id": 42,
  "config_updated": true,
  "outcome_id": 101
}
```

**What happens on accept:**
```
1. Validate suggestion belongs to user, status='pending'
2. Load current user_configs.config_json
3. Apply change (e.g., set source_weights.techcrunch = 1.3)
4. Save updated user_configs
5. Update config_suggestions.status = 'accepted', resolved_at = now
6. Insert into suggestion_outcomes with rich snapshot:
   - config_before: old config
   - config_after: new config
   - evidence_summary: copied from suggestion
7. Update user_preference_profiles (increment acceptance stats)
8. Return success
```

#### POST /api/suggestions/{id}/reject

Reject a suggestion → stores outcome only (no config change).

```
Request:  POST /api/suggestions/42/reject
Headers:  Cookie: session_id=...
Body:     {} (optional: {"user_reason": "I like TheVerge"})

Response:
{
  "success": true,
  "suggestion_id": 42,
  "outcome_id": 102
}
```

**What happens on reject:**
```
1. Validate suggestion belongs to user, status='pending'
2. Update config_suggestions.status = 'rejected', resolved_at = now
3. Insert into suggestion_outcomes with:
   - outcome: 'rejected'
   - user_reason: if provided
   - config_before: current config (no config_after since no change)
4. Update user_preference_profiles (increment rejection stats)
5. Return success
```

#### POST /api/suggestions/accept-all

Bulk accept all pending suggestions.

```
Request:  POST /api/suggestions/accept-all
Headers:  Cookie: session_id=...

Response (partial success with per-item results):
{
  "success": true,
  "accepted_count": 2,
  "results": [
    {"suggestion_id": 42, "status": "accepted"},
    {"suggestion_id": 43, "status": "failed", "error": "already_resolved"},
    {"suggestion_id": 44, "status": "accepted"}
  ]
}
```

### Integration with Existing Tables

| Existing Table | How Config Advisor Uses It |
|----------------|---------------------------|
| `user_configs` | Read current config, write on accept |
| `item_feedback` | Read for `query_user_feedback` tool |
| `users` | Validate user_id exists |
| `source_weight_snapshots` | Not used directly (different learning loop) |

**Note:** `source_weight_snapshots` is for the automated learning loop (Milestone 3b). Config advisor suggestions are user-initiated and go directly to `user_configs`.

---

## Guardrails & Cost Controls

### Cost Guardrails

| Guardrail | Implementation | Rationale |
|-----------|----------------|-----------|
| **1 run/user/day** | Check `runs` table for `run_type='advisor'` + `user_id` + today | Prevent runaway costs |
| **Max 50 turns** | Turn counter in `run_advisor()` loop | Bound agent compute |
| **gpt-4o model** | Hardcoded in `advisor.py` | Cost-effective reasoning |
| **Per-surface budget** | Separate caps for ingest vs advisor | Isolated cost control |
| **Token budget** | Track via `runs` table with `run_type='advisor'` | Unified cost tracking |

**Budget Caps (Per-Surface Isolation):**

| Surface | Daily Cap | Rationale |
|---------|-----------|-----------|
| Summaries (`run_type='ingest'`) | $5.00 | Existing cap via `LLM_DAILY_CAP_USD` |
| Advisor (`run_type='advisor'`) | $1.00 | 1 run/user/day, ~$0.10-0.50 each |

**Budget check (in run_advisor):**
```python
ADVISOR_DAILY_CAP_USD = float(os.getenv("ADVISOR_DAILY_CAP_USD", "1.00"))

def run_advisor(user_id: str, conn) -> dict:
    today = date.today().isoformat()
    today_cost = get_daily_spend_by_type(conn, day=today, run_type="advisor")
    if today_cost >= ADVISOR_DAILY_CAP_USD:
        return {"status": "budget_exceeded", "reason": "Daily advisor budget reached"}
    # ... run agent ...
```

**Cost recording pattern:**
```python
from src.repo import start_run, update_run_llm_stats, finish_run_ok

# At start
start_run(conn, run_id=run_id, started_at=started_at, received=0,
          run_type="advisor", user_id=user_id)

# After agent loop
update_run_llm_stats(conn, run_id=run_id, cache_hits=0, cache_misses=0,
    total_cost_usd=total_cost_usd, saved_cost_usd=0.0, total_latency_ms=total_latency_ms)

# On success
finish_run_ok(conn, run_id=run_id, finished_at=finished_at, ...)
```

**Note:** `run_type` column already exists in `runs` table (default='ingest'). New `get_daily_spend_by_type()` repo function aggregates costs by type.

### Safety Guardrails

| Guardrail | Implementation | Rationale |
|-----------|----------------|-----------|
| **Weight bounds ±0.3** | Enforced in `write_suggestion` validation | Prevent extreme swings |
| **Weight range [0.1, 2.0]** | Clamp final value | Never zero out or 10x a source |
| **No auto-apply** | Suggestions always `status='pending'` | User decides |
| **User isolation** | All queries scoped by `user_id` | No cross-user leakage |

**Bounds enforcement:**
```python
MAX_WEIGHT_CHANGE = 0.3
MIN_WEIGHT = 0.1
MAX_WEIGHT = 2.0

def validate_weight_change(current: float, suggested: float) -> float:
    delta = suggested - current
    if abs(delta) > MAX_WEIGHT_CHANGE:
        # Clamp to max change
        suggested = current + (MAX_WEIGHT_CHANGE if delta > 0 else -MAX_WEIGHT_CHANGE)
    return max(MIN_WEIGHT, min(MAX_WEIGHT, suggested))
```

### Quality Guardrails

| Guardrail | Implementation | Rationale |
|-----------|----------------|-----------|
| **Min 3 evidence items** | `write_suggestion` rejects if < 3 | No thin suggestions |
| **Min 7 days history** | `query_user_feedback` checks | Need pattern emergence |
| **Min 10 feedback items** | `query_user_feedback` checks | Statistical significance |
| **No duplicate suggestions** | Check pending for same field+value | Avoid spam |
| **Max 3 suggestions/run** | Agent stops after 3 written (max 1 source + 1 topic + 1 flex) | Quality over quantity, reduce overwhelm |

### User Protection

| Protection | How |
|------------|-----|
| **Transparent reasoning** | Every suggestion includes `reason` explaining why |
| **Evidence shown** | UI displays which items supported the suggestion |
| **Easy reject** | One click to reject, reason optional |
| **Undo via config** | User can always manually adjust config later |
| **No pressure** | Suggestions sit in `pending` until user acts |

### Failure Modes & Recovery

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Agent times out | 50 turns reached | Partial results saved, user notified |
| Tool fails | Exception in tool | Agent retries once, then skips |
| No patterns found | Agent reasoning | Returns 0 suggestions with explanation |
| All suggestions rejected (validation) | write_suggestion failures | Log for debugging, return empty |
| DB write fails | Exception | Rollback, return error to user |

### Edge Cases & Failure Modes

| Edge Case | Detection | Handling |
|-----------|-----------|----------|
| **Insufficient data** | <10 feedback items OR <7 days history | Exit early with "need more feedback" message |
| **Conflicting signals** | High like-rate but strong negative tags (e.g., "hype") | Agent reasons about conflict, may skip suggestion |
| **Config changed after suggestion** | Config differs from `config_before` snapshot | Accept revalidates current config before applying |
| **Weight bounds exceeded** | Suggested change > ±0.3 OR final > 2.0 or < 0.1 | Clamp to bounds, note in validation_notes |
| **Duplicate suggestion** | Same `field + suggested_value` already pending | Reject with "duplicate" error |
| **Stale suggestions** | No action after N days | Mark `status='expired'` (or `superseded` if new run) |
| **Concurrent accept** | Two accepts in quick succession for same suggestion | DB constraint + idempotent check (already accepted = no-op) |
| **Agent failure mid-run** | Timeout, error, or max turns reached | Partial results saved, user sees what was written |
| **All suggestions fail validation** | Every write_suggestion returns success=false | Return empty suggestions with skipped[] explaining why |
| **User has no config overrides** | `user_configs` row doesn't exist | Create on first accept (not on agent run) |

### Observability & Logging

**Structured log events (emit on each occurrence):**

| Event | When | Data |
|-------|------|------|
| `advisor_run_started` | Agent invocation begins | `{user_id, trigger: "ui"|"scheduled"}` |
| `advisor_run_completed` | Agent finishes successfully | `{user_id, suggestions_count, turns, cost_usd}` |
| `advisor_run_skipped` | Insufficient data or rate limited | `{user_id, reason}` |
| `suggestion_written` | write_suggestion succeeds | `{user_id, suggestion_id, type}` |
| `suggestion_rejected_validation` | write_suggestion fails | `{user_id, type, error, evidence_count}` |
| `suggestion_accepted` | User accepts suggestion | `{user_id, suggestion_id, type}` |
| `suggestion_rejected` | User rejects suggestion | `{user_id, suggestion_id, type, user_reason}` |

### Monitoring & KPIs

Track these metrics for health:

| Metric | Source | Alert If |
|--------|--------|----------|
| Suggestions/run | `config_suggestions` | Avg drops below 1 |
| Accept rate | `suggestion_outcomes` | Drops below 30% |
| Accept rate by type | `suggestion_outcomes` | Any type drops below 20% |
| Agent turns/run | Logging | Avg exceeds 30 |
| Validation failure rate | `write_suggestion` logs | >50% of attempts |
| Cost/run | `runs` where `run_type='advisor'` | Exceeds $0.50 |

---

## Output Format

```json
{
  "suggestions": [
    {
      "type": "add_topic",
      "field": "topics",
      "value": "Kubernetes",
      "confidence": "high",
      "reasoning": "Appears in 4 of 5 liked items. User consistently engages with container/orchestration content.",
      "evidence": [
        {"url": "...", "title": "...", "feedback": "liked"},
        {"url": "...", "title": "...", "feedback": "liked"}
      ],
      "expected_impact": "More Kubernetes articles will rank higher in future digests"
    }
  ],
  "skipped": [
    {
      "hypothesis": "Reduce theverge weight",
      "reason_skipped": "Only 3 items from source, insufficient data for confidence"
    }
  ],
  "meta": {
    "items_analyzed": 25,
    "patterns_found": 3,
    "suggestions_generated": 4,
    "suggestions_after_validation": 2,
    "run_id": "...",
    "user_id": "..."
  }
}
```

---

## Strategy: Build Phases

### Phase 1: Core Agent + Tools (v1)

**Goal:** Working agent that can generate validated suggestions

1. Define agent persona and prompt
2. Implement 6 core tools
3. Create reasoning loop
4. Basic validation
5. Output to `config_suggestions` table

**Deliverables:**
- `agents/config_advisor/` directory
- Agent prompt file
- Tool implementations
- Integration with existing DB

### Phase 2: Self-Critique + Refinement (v1.5)

**Goal:** Agent that catches its own mistakes

1. Add `self_critique` tool
2. Confidence scoring
3. Reasoning traces in output
4. Handle edge cases (no data, conflicting signals)

**Deliverables:**
- Enhanced output with confidence
- Critique step in loop
- Edge case handling

### Phase 3: Memory + Learning (v2)

**Goal:** Agent that improves over time

1. Track acceptance/rejection history
2. Per-user preference learning
3. Adapt suggestions based on past outcomes
4. Agent "remembers" what worked

**Deliverables:**
- `suggestion_outcomes` table
- Memory retrieval tool
- Adaptive prompting

---

## What Changes From Current Design

| Current Design | Agent Design |
|----------------|--------------|
| `jobs/suggest_config.py` | `agents/config_advisor/` directory |
| Single LLM call | Multi-turn agent loop |
| Validation in Python | Validation as agent tool |
| Static prompt | Dynamic prompt with context |
| No memory | Tracks history in DB or files |
| `src/config_advisor.py` | Tools in agent directory |

---

## Resolved Questions

*Answered via [Anthropic docs](https://code.claude.com/docs/en/sub-agents) + [claude-mem](https://github.com/thedotmack/claude-mem) research*

### 1. Where does agent live?

**Answer:** `.claude/agents/config-advisor.md`

**Note:** This is a top-tier, senior-engineering-level agent — distinct from the review agents (cost-risk-reviewer, etc.) which are pattern-scanning agents. Different purpose, different design.

**Learning patterns directory:** TBD — will decide later whether this agent needs `.claude/rules/config-advisor/` or a different approach.

**Why this path:** Version controlled, project-level, consistent with Anthropic docs.

### 2. How is it invoked?

**Answer:** Two paths, same `run_advisor()` function

| Trigger | Implementation | When |
|---------|----------------|------|
| **UI button** | `POST /api/suggestions/generate` → `src/advisor.py` → OpenAI API | User clicks "Get Suggestions" on `/ui/config` |
| **Scheduled** | `jobs/run_advisor.py` → `src/advisor.py` → OpenAI API | Every 7 days per user |

**UI flow:**
```
User on /ui/config clicks "Get Suggestions"
    │
    ▼
POST /api/suggestions/generate
    │
    ├── Check: already ran today? → return existing (idempotent)
    ├── Check: user has enough feedback? → return "insufficient data"
    │
    ▼
src/advisor.py:run_advisor(user_id, conn)
    │
    ├── Load system prompt from .claude/agents/config-advisor.md
    ├── Call OpenAI with function schemas (tools)
    ├── Loop: handle tool calls (max 50 turns)
    │     └── Dispatch to advisor_tools.py functions
    ├── Insert run into `runs` table with run_type='advisor'
    │
    ▼
Return {status: "completed", suggestion_ids: [...]}
    │
    ▼
UI fetches GET /api/suggestions → displays cards
```

**Scheduled flow:**
```
Task Scheduler / cron
    │
    ▼
python jobs/run_advisor.py --user-id abc123
    │
    ├── Open DB connection
    ├── Check: already ran this week? → exit
    │
    ▼
src/advisor.py:run_advisor(user_id, conn)
    │
    (same as UI flow)
    │
    ▼
Exit (suggestions waiting for user on next visit)
```

**Key:** Both flows call the same `run_advisor()` function. No divergence. Agent prompt loaded from `.claude/agents/config-advisor.md` (frontmatter is documentation only).

### 3. Tool implementation?

**Answer:** 3-Layer Python Architecture (NOT MCP)

Config advisor tools are implemented as Python functions, not MCP tools:

```
┌─────────────────────────────────────────────────────────────────┐
│  src/advisor.py — ORCHESTRATION ONLY                            │
│                                                                  │
│  ├── TOOL_SCHEMAS = [...]        # OpenAI function definitions  │
│  ├── SYSTEM_PROMPT = "..."       # Loaded from agent file       │
│  ├── run_advisor(user_id, conn)  # Main entry point             │
│  └── _handle_tool_call(name, args, conn)  # Dispatch to tools   │
│                                                                  │
│  Responsibilities:                                               │
│  - OpenAI API calls                                              │
│  - Function calling loop                                         │
│  - Turn limiting (MAX_TURNS=50)                                  │
│  - Cost tracking (insert into runs with run_type='advisor')     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  src/advisor_tools.py — BUSINESS LOGIC + VALIDATION             │
│                                                                  │
│  ├── query_user_feedback(user_id, conn) -> dict                 │
│  │     - Calls repo for raw feedback                            │
│  │     - Applies smart curation (stratified sampling)           │
│  │     - Computes source_patterns, tag_patterns                 │
│  │     - Returns ~2000 tokens max                               │
│  │                                                               │
│  ├── query_user_config(user_id, conn) -> dict                   │
│  │     - Calls repo for user_configs + active_weights           │
│  │     - Merges into single view                                │
│  │     - Returns ~500 tokens                                    │
│  │                                                               │
│  ├── get_user_profile(user_id, conn) -> dict                    │
│  │     - Calls repo for preference profile                      │
│  │     - Returns acceptance stats, patterns, trends             │
│  │     - Returns ~500 tokens                                    │
│  │                                                               │
│  ├── write_suggestion(user_id, data, conn) -> dict              │
│  │     - VALIDATES: evidence grounding, bounds, duplicates      │
│  │     - If valid: calls repo to insert                         │
│  │     - Returns {success, suggestion_id} or {error, details}   │
│  │                                                               │
│  └── get_suggestion_outcomes(user_id, query, conn) -> dict      │
│        - 3-layer retrieval (search → timeline → detail)         │
│        - Returns based on query.layer parameter                 │
│                                                                  │
│  Responsibilities:                                               │
│  - All validation logic (server-side, not in LLM)               │
│  - Data curation and aggregation                                │
│  - Token budget enforcement per tool                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  src/repo.py — DB CRUD ONLY (no business logic)                 │
│                                                                  │
│  Existing functions used by advisor_tools.py                    │
│  New functions added for config advisor (pure SQL, no logic)    │
└─────────────────────────────────────────────────────────────────┘
```

**Why this separation matters:**
- `repo.py` stays pure — no risk of mixing concerns
- `advisor_tools.py` is testable without LLM — mock repo, verify logic
- `advisor.py` is testable without DB — mock tools, verify orchestration
- Validation is **server-side** — LLM can't bypass it

**MCP server status:** `mcp-servers/verifier/server.py` is **UNCHANGED**. It's still used by Claude Code review agents (cost-risk-reviewer, etc.). Config advisor does NOT use MCP — it calls Python directly via OpenAI function calling.

**Token budget per tool:**

| Tool | Max Tokens | Rationale |
|------|------------|-----------|
| `query_user_feedback` | ~2000 | 50 items + patterns |
| `query_user_config` | ~500 | Single config object |
| `get_user_profile` | ~500 | Single profile object |
| `write_suggestion` | ~100 | Just success/error |
| `get_suggestion_outcomes` | ~1000 | Depends on layer |

---

## Tool Design Philosophy

**Principle: Tools are smart, not dumb pipes.**

The agent's context window is precious. Tool functions should:
- Do heavy lifting server-side (ML, statistics, aggregation)
- Return curated, high-signal data
- Include computed patterns the agent can reason about
- Provide confidence levels so agent knows what's solid vs thin

### query_user_feedback — Smart Curation

**Input:** `user_id` (required)

**Input signals available (in database):**
- Thumbs up (`useful = 1`)
- Thumbs down (`useful = 0`)
- Reason tags (written feedback from LLM-suggested options)

**Minimum thresholds (agent won't run without these):**

| Threshold | Value | Rationale |
|-----------|-------|-----------|
| Minimum days of history | 7 | Need time for patterns to emerge |
| Minimum feedback items | 10 | Statistical significance |
| Minimum items with reason tags | 10 | Deeper signal for preference profiling |

If thresholds not met → Tool returns `{"insufficient_data": true, "reason": "..."}` and agent short-circuits.

**Problem:** User may have 250+ feedback items. Dumping all = token explosion.

**Solution:** advisor_tools applies intelligent selection server-side.

**Possible techniques (implementation decides):**
- Stratified sampling (representation across sources, time, +/-)
- Recency weighting (recent items more likely selected)
- Diversity sampling (avoid 10 items from same source)
- Signal prioritization (items with reason_tags > bare thumbs)
- Trend detection (flag if recent differs from historical)

**Output structure:**
```json
{
  "curated_items": [
    // 30-50 representative items, not hundreds
    {
      "url": "...",
      "title": "...",
      "source": "techcrunch",
      "useful": 1,
      "reason_tag": "finally explained well",
      "feedback_date": "2026-01-28",
      "days_ago": 3
    }
  ],
  "source_patterns": {
    "techcrunch": {"like_rate": 0.85, "sample_size": 40, "confidence": "high"},
    "theverge": {"like_rate": 0.35, "sample_size": 15, "confidence": "medium", "trend": "declining"}
  },
  "tag_patterns": {
    "values": {"clarity": 12, "depth": 8},
    "dislikes": {"hype": 7, "paywall": 5}
  },
  "meta": {
    "total_feedback_available": 250,
    "items_returned": 45,
    "date_range": "2025-06-15 to 2026-01-28"
  }
}
```

**Agent receives:** Pre-computed patterns + representative sample + confidence levels.

### query_user_config — Merged View

**Input:** `user_id` (required)

**Output structure:**
```json
{
  "config": {
    "topics": ["AI", "kubernetes", "security"],
    "source_weights": {"techcrunch": 1.2, "arstechnica": 1.3},
    "keyword_boosts": {"million": 0.5},
    "recency_half_life_hours": 24.0,
    "ai_score_alpha": 0.1
  },
  "active_weights": {
    // After learning loop adjustments
    "techcrunch": 1.25,
    "theverge": 0.85
  },
  "has_user_overrides": true,
  "last_weight_update": "2026-01-21"
}
```

**Agent sees:** Full config state including learning loop effects.

### write_suggestion — Validate + Store

**Why validation is built-in (not a separate tool):**
- Reduces round-trips (agent calls once, not twice)
- Forces atomic operation (can't write unvalidated suggestions)
- Simpler agent reasoning (no "validate then write" sequence)

**Note:** The existing `grounding.py` validates LLM citation outputs (exact substring match). That's a different concern — it ensures summaries are grounded in article evidence. Config advisor validation ensures suggestions are grounded in user feedback patterns.

**Input:**
```json
{
  "user_id": "abc123",
  "suggestion_type": "boost_source",     // add_topic, remove_topic, boost_source, reduce_source
  "field": "source_weights",             // topics, source_weights
  "target_key": "techcrunch",            // source name for boost/reduce, null for topics
  "current_value": "1.0",                // null for add_topic
  "suggested_value": "1.3",              // new topic name or weight
  "evidence_items": [                    // Required: what supports this (url is canonical key)
    {"url": "...", "title": "...", "feedback": "liked", "reason_tag": "finally explained well", "item_id": 123},
    {"url": "...", "title": "...", "feedback": "liked", "reason_tag": null, "item_id": null}
  ],  // Note: item_id is optional (populated if exact URL match found in news_items)
  "reason": "User liked 8/10 articles from this source"
}
```

**Validation rules (enforced server-side in `write_suggestion`):**

| Check | Rule | On Fail |
|-------|------|---------|
| **Evidence grounding** | All evidence_items.url must exist in `item_feedback` for same user | Reject: "evidence not grounded" |
| **Min evidence count** | `len(evidence_items) >= 3` | Reject: "insufficient evidence (need 3+)" |
| **Uniqueness** | No pending suggestion for same `field + suggested_value` | Reject: "duplicate suggestion pending" |
| **Cooldown** | Same target not suggested/resolved in last 10 days | Reject: "target on cooldown" |
| **Weight delta bounds** | Weight change ≤ ±0.3 from current | Clamp to max delta, continue |
| **Weight absolute bounds** | Final weight in `[0.1, 2.0]` | Clamp to range, continue |
| **Source relevance** | For source suggestions: source must appear in user's feed history | Reject: "source not found in history" |
| **Topic relevance** | For topic suggestions: topic string should appear in evidence item titles | Reject: "topic not grounded in evidence" |
| **Status transitions** | Only valid: `pending → accepted/rejected/superseded` | Reject: "invalid status transition" |

**Why server-side validation:**
- Agent can't bypass checks (even if it hallucinates)
- DB stays clean (no ungrounded suggestions stored)
- Single source of truth for validation logic
- Simpler agent prompt (doesn't need to re-implement rules)

**Output:**
```json
{
  "success": true,
  "suggestion_id": 42,
  "status": "pending",
  "validation_notes": ["Weight clamped from 1.5 to 1.3 (max +0.3)"]
}
```

Or on validation failure:
```json
{
  "success": false,
  "error": "insufficient evidence",
  "details": "Need at least 3 evidence items, got 2"
}
```

**Agent flow:**
```
1. Agent gathers evidence from query_user_feedback
2. Agent reasons about patterns → forms suggestion
3. Agent calls write_suggestion with evidence
4. advisor_tools validates and stores (or rejects)
5. Agent receives result, continues or adjusts
```

**Excluded:** Bash, Write, Edit — agent suggests, doesn't modify files

### 5. Agent YAML frontmatter

**Note:** Frontmatter is **DOCUMENTATION ONLY** — not used at runtime. The agent prompt is loaded by `src/advisor.py` and tools are defined as OpenAI function schemas in Python.

```yaml
---
# YAML frontmatter is DOCUMENTATION ONLY (not used at runtime)
name: config-advisor
description: Analyzes user feedback and suggests config improvements
model: gpt-4o
---

You are a personalization expert helping optimize this user's news digest.
Analyze their feedback patterns and recommend configuration changes that
would improve relevance.

[... full prompt ...]
```

**At runtime:**
```python
# src/advisor.py

def load_agent_prompt() -> str:
    path = Path(".claude/agents/config-advisor.md")
    content = path.read_text()
    # Skip YAML frontmatter, return prompt body
    if content.startswith("---"):
        _, _, body = content.split("---", 2)
        return body.strip()
    return content
```

**Why this design:**
- Prompt lives in markdown file (version controlled, easy to edit)
- Tools defined in Python as `TOOL_SCHEMAS` (OpenAI function calling format)
- Frontmatter documents intent but runtime ignores it
- Model hardcoded in `advisor.py` for cost control

### 6. Input parameters

| Parameter | Required | Source | How Passed |
|-----------|----------|--------|------------|
| `user_id` | Yes | Session (UI) or CLI arg (scheduled) | Injected into prompt |
| `window_days` | No | Default 14 | Agent decides via tool call |
| `run_mode` | No | "interactive" or "scheduled" | Optional context |

**Prompt template:**
```
You are analyzing feedback for user: {{user_id}}

Your task: Generate config suggestions based on their feedback patterns.

Use your tools to:
1. Query their recent feedback (last 14 days)
2. Analyze patterns in liked/disliked items
3. Build preference profile from reason tags
4. Generate grounded suggestions
5. Write validated suggestions to the database

Guidelines:
- Only suggest changes with clear evidence
- Quality over quantity (2-3 good suggestions beat 5 weak ones)
- Express confidence level for each suggestion
```

**Why `user_id` in prompt (not just tool)?**
- Agent needs it for every tool call
- Prevents agent from "forgetting" which user
- Clear scope from the start

**Why `window_days` via tool?**
- Agent can adapt (start 14 days, expand to 30 if insufficient data)
- Flexibility without prompt complexity

### 7. Memory storage?

**Answer:** See [MEMORY_DESIGN.md](MEMORY_DESIGN.md) for complete architecture.

**Summary:**
- 3-layer storage: Raw events (DB) → Computed profiles (DB) → Curated insights (MD)
- 3-layer retrieval: Search (~50 tokens) → Timeline (~200) → Detail (~500)
- 10x token savings by filtering before fetching
- Phased: v1 tag-based, v2 hybrid search, v3 compaction

---

## Deep Preference Profiling

The agent analyzes **reason tags** to understand *why* users like or dislike content — not just what they liked.

**Reason tags reveal preferences that pure like/dislike counts miss:**
- "Finally explained well" → values clarity
- "Too much hype" → dislikes sensationalism
- "Paywall issues" → friction signal
- "Already knew this" → advanced user

**How this informs suggestions:**

| Profile Signal | Suggestion |
|----------------|------------|
| "too much hype" on TheVerge 4x | Reduce TheVerge weight |
| "finally explained well" on deep dives | Boost explainer sources |
| "paywall issues" on NYT | Reduce NYT (friction) |
| "already knew this" on basic articles | Boost niche/technical sources |

**Full architecture:** See [MEMORY_DESIGN.md](MEMORY_DESIGN.md) for profile structure, storage, and retrieval patterns.

---

## Next Steps

**Design Phase Complete ✅**

1. ~~Agent file location~~ → `.claude/agents/config-advisor.md`
2. ~~Invocation~~ → UI button + scheduled job
3. ~~Tool implementation~~ → Implement advisor_tools.py (Python tools), repo CRUD, OpenAI tool schemas
4. ~~Memory architecture~~ → See MEMORY_DESIGN.md
5. ~~Tool specifications~~ → Core tools designed
6. ~~Reasoning loop~~ → Detailed flow with branching, errors, success criteria
7. ~~DB integration + API endpoints~~ → Full API spec with accept/reject flows
8. ~~Guardrails + cost controls~~ → Cost, safety, quality, monitoring

---

## Implementation Checklist

### Step 0: Config-Ranking Integration (BLOCKING)
- [ ] Move `get_effective_rank_config()` to shared module
- [ ] Update `jobs/daily_run.py` to use it
- [ ] Update `jobs/build_digest.py` to use it
- [ ] Update `src/main.py` ranking routes to use it
- [ ] Add test: accepted suggestion changes ranking

### Step 1: DB Schema + Repo
- [ ] Add `config_suggestions` table
- [ ] Add `suggestion_outcomes` table
- [ ] Add `user_preference_profiles` table
- [ ] Add indexes (run_type column already exists)
- [ ] Add repo CRUD functions
- [ ] Add `get_daily_spend_by_type()` repo function
- [ ] Unit tests for repo functions

### Step 2: Advisor Tools
- [ ] Create `src/advisor_tools.py`
- [ ] Implement `query_user_feedback()` with curation
- [ ] Implement `query_user_config()` with merge
- [ ] Implement `get_user_profile()`
- [ ] Implement `write_suggestion()` with validation
- [ ] Implement `get_suggestion_outcomes()` with 3-layer
- [ ] Unit tests for each tool (mock repo)

### Step 3: API Endpoints
- [ ] `POST /api/suggestions/generate` (idempotent)
- [ ] `GET /api/suggestions`
- [ ] `POST /api/suggestions/{id}/accept`
- [ ] `POST /api/suggestions/{id}/reject`
- [ ] `POST /api/suggestions/accept-all`
- [ ] Update `/debug/costs` for per-surface breakdown
- [ ] Integration tests for endpoints

### Step 4: UI Surface
- [ ] "Get Suggestions" button on `/ui/config`
- [ ] Suggestion cards with reason + evidence
- [ ] Accept/Reject buttons
- [ ] "Insufficient data" state
- [ ] "Already generated today" state
- [ ] Loading state

### Step 5: Agent Runtime
- [ ] Create `src/advisor.py`
- [ ] Load prompt from `.claude/agents/config-advisor.md`
- [ ] Define `TOOL_SCHEMAS` (OpenAI function calling format)
- [ ] Implement `run_advisor()` with function calling loop
- [ ] Implement `_handle_tool_call()` dispatcher
- [ ] Turn limiting (MAX_TURNS=50)
- [ ] Cost tracking (start_run → update_run_llm_stats → finish_run_ok)
- [ ] Budget cap check
- [ ] Create `jobs/run_advisor.py` for scheduled runs

### Step 6: Tests + Evals
- [ ] Unit tests: repo, tools, advisor
- [ ] Integration tests: API endpoints
- [ ] **Config merge test:** Accepted suggestion changes ranking score
- [ ] **Validation tests:** Evidence grounding, duplicate suppression, weight clamp
- [ ] **Idempotent test:** Same-day generate call returns existing suggestions
- [ ] **User isolation test:** User A cannot read/accept User B's suggestions
- [ ] Deterministic eval fixtures (no LLM)

---

## References

- **Memory Architecture:** [MEMORY_DESIGN.md](MEMORY_DESIGN.md)
- **AI Capabilities:** [AI_CAPABILITIES.md](AI_CAPABILITIES.md)
- **Status:** [STATUS.md](STATUS.md)
- **Current agents:** `.claude/agents/`
- **Agent rules:** `.claude/rules/`

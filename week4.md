# Week 4 — AI Engineering Execution Plan (Current)

## North Star
Finish news-digest-engine as an operable AI system while mastering AI engineering under pressure: trust boundaries, eval gates, observability, and safe iteration.

Week 4 is not about features for their own sake. It is about shipping changes safely while preserving:
- determinism where required
- safe AI boundaries where used
- debuggability and auditability
- measurable quality (evals)
- real user value (UI + delivery)

---

## Current State (Snapshot)
- Milestone 1: UI + HTML hardening — COMPLETE
- Milestone 2: Cost guardrail + debug — COMPLETE
- Milestone 3a: Feedback reasons — COMPLETE
- Milestone 3b: Source-weight learning loop — COMPLETE
- Milestone 3c: TF-IDF AI score — COMPLETE
- Milestone 4: User auth + sessions + per-user isolation — COMPLETE
- Review agents: 5 self-learning agents — COMPLETE
- Overnight automation: 7-step workflow — COMPLETE + TESTED
- Codex cost controls: $1 cap, retry, pre-flight — COMPLETE
- End-to-end testing: Both paths verified — COMPLETE
- Ruff linter: `make lint` — COMPLETE
- **Milestone 4.5: AI Config Advisor Agent — IN PROGRESS** (see AGENT_DESIGN.md)
- Tests: 313 passed, 17 skipped

---

## Week 4 Accomplishments (to date)

### Milestone 4 — Multi-User Authentication (COMPLETE)
**What:** Added user authentication, session management, and per-user data isolation across the entire system.

**Why it matters:** Without user isolation, feedback from one user would pollute another's rankings. A multi-user system requires strict boundaries so each user's preferences evolve independently.

**Why we did it:** The weight learning loop (Milestone 3b) and TF-IDF AI score (3c) are user-specific features. They only make sense when feedback is scoped to the individual.

**Deliverables:**
- `users`, `user_configs`, `sessions` tables
- bcrypt password hashing in `src/auth.py`
- Session expiry enforcement
- Auth endpoints (register, login, logout, me)
- Admin-only RBAC on `/debug/*` routes
- `--user-id` flags on all jobs
- 33 tests in `tests/test_auth.py`

---

### Review Agents — Self-Learning Code Reviewers (COMPLETE)
**What:** Created 5 specialized review agents that scan the codebase, write findings, and learn from each run.

**Why it matters:** Automated code review catches issues humans miss. Self-learning means agents improve over time without manual rule updates. Human overrides ensure agents don't repeat mistakes.

**Why we did it:** As the codebase grows, manual review doesn't scale. Agents provide consistent coverage for security (user isolation), correctness (scoring integrity), cost control, and test coverage.

**Agents created:**
| Agent | Purpose |
|-------|---------|
| cost-risk-reviewer | Detect unbounded API calls, missing budget caps |
| user-isolation-reviewer | Find missing `user_id` scoping that could leak data |
| scoring-integrity-reviewer | Validate ranking/scoring logic integrity |
| test-gap-reviewer | Identify untested code paths |
| ux-reviewer | Evaluate customer-facing UI (manual/on-demand) |

**Learning structure:**
```
.claude/agents/{agent}.md           ← Agent definition
.claude/rules/{agent}/
  ├── learned-patterns.md           ← Agent updates after each run
  ├── human-overrides.md            ← Human corrections (always wins)
  └── run-history.md                ← Audit log
artifacts/agent-findings.md         ← Consolidated findings
```

---

### Overnight Automation — Two-Phase Implementation (COMPLETE)
**What:** Automated overnight agent runs that produce findings for morning review.

**Why it matters:** Code review shouldn't wait for human availability. Running agents overnight means issues are surfaced before the next work session, reducing feedback loops from days to hours.

**Why we did it:** Manual agent invocation is tedious and easy to forget. Automation ensures consistent coverage. Two-phase approach gives flexibility (GitHub for proven CI, local for free runs).

#### Phase 1: GitHub Actions (PROVEN)
**File:** `.github/workflows/overnight-review.yml`

Successfully tested workflow that:
- Runs 4 code agents sequentially (serial execution per best practices)
- Each agent reads its instructions from `.claude/agents/{agent}.md`
- Writes findings to `artifacts/agent-findings.md`
- Updates learned patterns and run history
- Creates summary GitHub issue
- Commits artifacts back to repo

**Key learnings during implementation:**
- `claude_args` format with `--max-turns` and `--allowedTools` flags (not direct parameters)
- `git add -f` needed for `.gitignore`'d directories
- Workflow must exist on default branch to appear in Actions tab
- 50 max turns sufficient for review agents

#### Phase 2: Local Script (COMPLETE)
**File:** `scripts/overnight_local.bat`

Free alternative using Claude subscription (not API credits):
- Same 4 agents as GitHub Actions
- Run manually or via Windows Task Scheduler
- Includes summary generator step

**Usage:**
```powershell
scripts\overnight_local.bat           # Run all agents + summary
scripts\overnight_local.bat summary   # Run only summary step
```

---

### Summary Generator — Prioritized Action Plans (COMPLETE)
**What:** A 5th step that reads agent findings, verifies against actual code, and produces a prioritized morning action plan.

**Why it matters:** Raw agent findings are verbose. The summary extracts what matters, prioritizes by risk, and explains why each issue needs fixing. This is what you actually read in the morning.

**Why we did it:** Following Anthropic's artifact-based coordination pattern. Agents write raw findings, summary agent reads and synthesizes. Verification against actual code catches stale findings.

**Output structure:**
```markdown
# Overnight Summary - 2026-01-31

## Priority 1 (Critical - Fix Today)
| Issue | Location | Why This Matters | Risk | Agent |

## Priority 2 (Medium - Fix This Week)
...

## Recommended Fix Order
1. Fix X first because... (dependencies)
2. Then Y...

## Stale/Invalid Findings
(findings where code was already fixed)
```

**Follows Anthropic patterns:**
- Artifact-based coordination (agents → findings → summary)
- Verification before acting (reads actual code)
- Lightweight references (concise tables, not full dumps)
- Chained from main script (not nested subagents)

---

### Morning Review Workflow — Claude + Codex Loop (DOCUMENTED)
**What:** Defined the human-in-the-loop review process for acting on overnight findings.

**Why it matters:** Automation finds issues; humans decide fixes. The Claude → Codex → Claude → Codex loop provides multi-model validation before changes ship.

**Flow:**
```
Overnight: Agents run → findings → summary
Morning:   Human reads summary
           → Claude proposes fix tasks (STATUS.md)
           → Codex reviews plan (second opinion)
           → Claude implements fixes
           → Codex verifies changes
           → Human approves/rejects
           → make test confirms
```

**Script:** `scripts/overnight_local.bat`

---

### Codex Cost Controls — Production Safety (COMPLETE)
**What:** Added comprehensive cost controls to the Codex review step (Step 6).

**Why it matters:** OpenAI API calls cost money. Without guards, a malformed or oversized prompt could cause runaway costs. The $1 cap ensures overnight automation never surprises with a large bill.

**Implemented controls:**
| Control | Value | Purpose |
|---------|-------|---------|
| Hard cost cap | $1.00 | Fail if estimated cost exceeds |
| Token pre-flight | 50,000 max | Fail if prompt too large |
| Retry with backoff | 3 attempts | Handle 429/500/503 transient errors |
| Cost logging | Footer in fix-tasks.md | Visibility into actual spend |

**Actual costs observed:** $0.01-0.04 per run (well under cap).

---

### End-to-End Workflow Testing (COMPLETE)
**What:** Tested the full 7-step overnight workflow including the "no issues found" edge case.

**Why it matters:** The workflow must handle both "issues found" and "clean codebase" paths gracefully. Testing proves both paths work correctly before relying on automation.

**Test results:**
| Scenario | Steps Run | Result |
|----------|-----------|--------|
| Issues found | All 7 | Fixes implemented, 313 tests pass |
| No issues | 5-7 | Codex responds "Codebase looks clean", no changes made |

**Edge cases grilled:**
| Issue | Verdict |
|-------|---------|
| Step 5 fails | Accept - visible failure |
| UX agent missing | Intentional - requires server |
| Bash access risk | Accept - branch isolation |
| Concurrent runs | Accept - rare |
| make test hang | **Fixed** - added 5min timeout |

---

### Implementation Agent Timeout (COMPLETE)
**What:** Added 5-minute timeout rule for `make test` in Step 7.

**Why it matters:** Test suite takes ~108 seconds normally, but default Bash timeout is 120 seconds. Only 10% buffer. As tests grow, could timeout on valid runs.

**Change:** Added to `scripts/implement-prompt.txt`:
```
- Use 5 minute timeout (300000ms) for `make test` to allow for test suite growth
```

---

### Documentation Updates
- `STATUS.md`: Current state, milestone tracking, data model
- `week4.md`: Completed work summaries (this file)
- `future.md`: Deferred/backlog items
- `AGENT_DESIGN.md`: Config advisor agent architecture (NEW)
- `AI_CAPABILITIES.md`: All AI patterns — agents, MCPs, hooks, memory (NEW)

---

## What “AI Engineering” Means Here
AI is a component behind a boundary:
- LLM stage is optional
- system completes even if LLM refuses or fails
- no runtime agents controlling flow

Contracts over vibes:
- schema-first outputs
- grounding/citations or refusal
- deterministic fallbacks
- explicit failure taxonomy

Evals are infrastructure:
- regression gates (must stay green)
- capability checks (grow over time)
- eval reports are first-class artifacts

Separation of surfaces:
- customer UI: clarity + trust
- operator/debug: diagnosis + metrics
- artifacts: durable outputs
- no surface leaks another’s responsibilities

Learning loops must be controllable:
- feedback influences ranking only via explicit transforms
- bounded updates
- before/after eval deltas
- snapshot persistence

---

## Linting (Required)
Add a linter to keep quality stable as the codebase grows.
- Standard: Ruff
- Target: `ruff check` on CI or before merge
- Why: fast, deterministic, keeps style drift low

---

## Customer vs Operator UI (Target)

Customer UI (trust-first):
- Landing: redirect to most recent `/ui/date/{date}`
- Digest view: items + summaries/refusals + topics/tags + feedback controls
- Run rating (stars) for overall digest
- Left nav via hamburger menu:
  - History: list of dates + ratings; click opens digest for that date
  - Config: ranking preferences (phased)
  - Settings: placeholder
- No debug data on customer pages

Operator UI (owner view):
- Full diagnostics: run_id, failures, cost stats, artifacts, evals
- Can inspect what customers see for support/debug
- Strict separation from customer surfaces

---

## Tooling & Roles
Roles
- Codex (Architect/Reviewer): sequencing, acceptance criteria, design review
- Claude Code (Builder): implements on branches, writes tests, refactors in scope
- Human (Patrick): correctness boundaries, review diffs, run final tests, merge

Rule
- Agents build. Tests decide. Humans approve.

Hard lines
- no schema/grounding/refusal changes without explicit instruction
- no weakening of eval rules
- no skipping tests
- no direct merges by agents

---

## MCPs, Agents, Skills (Current + Planned)

**See `AI_CAPABILITIES.md` for full details.**

MCPs (Active)
- Verifier MCP: run tests + evals, summarize failures
- Playwright MCP: UI smoke tests
- Browserbase MCP: remote UI checks (optional)

Agents (Active)
- cost-risk-reviewer: unbounded API calls, missing budget caps
- user-isolation-reviewer: missing user_id scoping
- scoring-integrity-reviewer: ranking/scoring logic
- test-gap-reviewer: untested code paths
- ux-reviewer: customer UI clarity (on-demand)
- **config-advisor (NEW)**: suggests config improvements based on feedback

Skills (Planned for config-advisor)
- suggestion-safety-check: inline validation
- suggestion-eval: fixture-based regression testing

Hooks (Planned)
- post-accept-hook: backup config, log analytics
- pre-digest-hook: nudge about pending suggestions

---

## Milestones (Updated)

### Milestone 4 — Multi-User + Config (Next)
Goal: Multiple users, isolated configs, safe access.

Deliverables
- users + user_configs tables
- ranking scoped by user_id
- feedback scoped by user_id
- minimal auth (magic link or email/password)
- RBAC stub guarding /debug/*
- per-user weight snapshots (user_id on weight_snapshots already exists)

Tests
- user-scoped ranking test
- user-scoped feedback test
- auth smoke test

Tooling
- Claude Code for migrations + wiring + tests
- Context7 for auth/OAuth semantics if needed

---

### Milestone 4.5 — AI Configuration Advisor Agent (IN PROGRESS)
Goal: Build a **full AI agent** that analyzes user feedback and suggests config improvements.

**Why an agent (not just a job)?**
- Exploratory reasoning — discovers patterns, not just executes steps
- Rich tool environment — queries DB, validates suggestions, self-critiques
- Iterative refinement — generate → evaluate → improve cycle
- Memory and learning — tracks what users accept/reject over time

**v1 Scope:** Topics + sources only. Recency deferred to v2.

Deliverables
- Agent definition: `.claude/agents/config-advisor.md`
- Reasoning loop: explore → hypothesize → validate → critique → present
- Tool set: query feedback, compute stats, validate grounding, self-critique
- Memory: `suggestion_outcomes` table + 3-layer retrieval pattern
- UI surface: "Suggested updates" panel in `/ui/config`
- Invocation: user-triggered (UI) + scheduled (every 7 days)

Guardrails
- AI suggests; system never auto-applies
- Evidence required for every suggestion
- Self-critique before presenting
- Log suggestions + acceptance rate for learning

**Design Documents:**
- `AGENT_DESIGN.md` — Agent architecture, persona, tools, reasoning
- `AI_CAPABILITIES.md` — Skills, hooks, MCPs, memory patterns
- `STATUS.md` — Data model, API endpoints, acceptance criteria

---

### Milestone 5 — Email Delivery
Goal: System delivers the digest automatically.

Deliverables
- jobs/send_digest --date --user_id
- SMTP integration (SendGrid/Mailgun preferred)
- Email-safe HTML reuse
- Audit log entries for sends
- Tests for payload correctness

---

## Ingestion Strategy (Multi-User Reality)
- Short-term: shared public RSS list (works for demos)
- Mid-term: per-user feed lists (user_feeds table)
- Paid sources: use official APIs or feeds; do not scrape paywalled sites
- If a source is unsupported, show a clear UI message

---

## Evals & Fixtures (Must-Have)
- Ranking evals remain fixture-driven and deterministic
- New fixtures for:
  - weight updates (already added)
  - ai_score (already added)
  - multi-user ranking (to add)
- Regression guard before merging

---

## Next Steps (Detailed, Immediate)
1. ~~Fix critical bugs found by review agents~~ ✅ DONE
2. ~~Add OpenAI integration~~ ✅ DONE (Codex review in Step 6)
3. ~~Merge to main~~ ✅ DONE (removed claude-edits intermediate branch)
4. ~~Add Ruff linter~~ ✅ DONE (`make lint`)
5. ~~Draft AI Configuration Advisor spec~~ ✅ DONE (see AGENT_DESIGN.md)
6. **Build config-advisor agent** — IN PROGRESS
   - Create `.claude/agents/config-advisor.md`
   - Implement agent tools (query, validate, critique)
   - Add memory tables and 3-layer retrieval
   - Build UI panel in `/ui/config`
7. Plan Email Delivery (Milestone 5) — NEXT

---

## Backlog (Deprioritized)
- Next.js rewrite
- Full OAuth (Gmail) if SMTP is sufficient
- Redis caching / async ingestion
- Runtime agentization

---

## Throughline
We are building a system that is:
- trusted by users
- debuggable by operators
- improvable without regressions
- delivered automatically
- accelerated by AI tools without losing control

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
- Milestone 1: UI + HTML hardening — complete
- Milestone 2: Cost guardrail + debug — complete
- Milestone 3a: Feedback reasons — complete
- Milestone 3b: Source-weight learning loop — complete
- Milestone 3c: TF-IDF AI score — complete; integration in scoring; tests/fixtures added

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

## MCPs, Agents, Skills (Recommended)

MCPs
- Verifier MCP: run tests + evals, summarize failures
- Playwright MCP: UI smoke tests
- Browserbase MCP: remote UI checks

Agents
- UX Reviewer: checks customer UI clarity (already defined)
- Scoring Integrity Reviewer (optional): sanity-check that ai_score is bounded and additive

Skills
- Snapshot regeneration skill (HTML / UI)
- Fixture generation skill (weights / ai_score / evals)

Hooks
- Post-commit push (already installed)
- Optional: eval-delta summarizer after ranking changes

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

### Milestone 4.5 — AI Configuration Advisor (New, Aggressive AI)
Goal: AI suggests config updates (topics/sources/recency) with evidence. User decides.

Deliverables
- Daily AI suggestion artifact (per user): top 3–5 recommended config changes
- Evidence links: which liked/disliked items drove suggestion
- UI surface: “Suggested updates” panel (accept/ignore)
- Cost budget: single LLM call per user/day, capped

Guardrails
- AI suggests; system never auto-applies
- Log suggestions + acceptance rate
- Evals compare baseline vs suggested config (preview mode)

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
1. Confirm ai_score applied everywhere the user sees rankings (UI + jobs + API)
2. Add Ruff linter to repo and CI/pre-merge step
3. Plan Milestone 4 schema + auth
4. Add user-scoped fixtures and tests
5. Draft AI Configuration Advisor spec (Milestone 4.5)

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

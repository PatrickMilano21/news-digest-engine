# Week 4 — AI Engineering Execution Plan (Progressive)

## North Star
Finish news-digest-engine as an operable AI system while becoming fluent at AI engineering under pressure: designing trust boundaries, enforcing contracts, running eval gates, operating user-facing surfaces, and iterating safely with AI tooling.

Week 4 is not about features for their own sake. It is about shipping changes safely while preserving:
- determinism where required
- safe AI boundaries where used
- debuggability and auditability
- measurable quality (evals)
- real user value (UI + delivery)

---

## What “AI Engineering” Means in This Repo
AI engineering here is not prompt hacking. It’s system design and operation.

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
- feedback can influence ranking only via explicit transforms
- bounded updates
- before/after eval deltas
- snapshot persistence

---

## Week 4 Invariants (Non-Negotiable)
- Deterministic core: same input → same ranking
- Eval gated: no merge without `make test` + relevant evals passing
- Observable: every run has run_id, failures_by_code, artifact paths
- No runtime agents: AI tooling assists humans, never production flow
- No silent intelligence: every tool use has explicit input/output and failure mode
- Customer-safe: refusals and missing content must be explained plainly

---

## Tooling & Roles (How We Actually Work)
Roles
- Codex (Architect/Planner): sequencing, acceptance criteria, design review
- Claude Code (Builder): implements on branches, writes tests, refactors in-scope
- Human (Patrick): owns correctness boundaries, reviews diffs, runs final tests, merges

Rule
- Agents build. Tests decide. Humans approve.

Hard lines (agents must not do)
- change schemas/grounding/refusal semantics without explicit instruction
- weaken eval rules or grading criteria
- bypass tests or skip reproduction steps
- commit/merge code

---

## Progressive Learning Ladder (Week 4)
Week 4 is structured to progressively add real AI engineering pressure.

Level 1 — Trust Surfaces (UI + Artifacts)
Goal: Users can understand outputs + refusals; artifacts match UI; tests prevent regressions.

Level 2 — Guardrails (Cost + Failure Under Pressure)
Goal: System degrades gracefully; cost is visible and bounded; failures are diagnosable without code.

Level 3 — Learning Loop (Feedback → Controlled Updates)
Goal: System adapts using explicit transforms + eval deltas + snapshots (no model magic).

Level 4 — Multi-user Reality (Users + Config + Isolation)
Goal: User-scoped configs and surfaces; access boundaries; auditability.

Level 5 — Delivery (Email)
Goal: Value is delivered automatically; failures are observable; audit log captures sends.

---

## Execution Workflow (Canonical)
For each ticket:

PLAN v1 (required)
- Objective
- Steps
- Files to touch
- Tests to add/update
- Done when

Execution loop
- Plan exists
- Claude builds on branch `agent/<ticket>`
- Run tests + evals (MCPs may help run/summarize)
- Human review (UI click + diff review + acceptance checklist)
- Merge when green

Acceptance checklist
- Tests pass locally
- UI clicked manually (happy + refusal case)
- No debug-only fields leak to UI
- Diff reviewed top-to-bottom
- Can explain change in 2 sentences

---

## Milestones (What We Ship, In Order)

### Milestone 1 — UI & HTML Hardening (Trust Surfaces)
AI engineering focus: user trust, refusal clarity, artifact alignment, regression safety.

Deliverables
- /ui/date/{date} is readable and customer-safe
- Refusals are standardized and plain-English
- Citations are readable and trust-building
- Run summary header gives context without debug noise
- digest_*.html is email-safe
- Shared components prevent UI/artifact divergence
- Snapshot + smoke tests guard against regressions

Tooling guidance
- Claude Code: templates + artifacts + tests
- MCPs: repo navigation, test runner, diff summary
- Skills: HTML formatting/snapshot generation if repeated
- Hooks: optional digest-built → summarize changes (dev only)
- Agents: allowed for template scaffolding and snapshot test boilerplate

### Milestone 2 — Cost Guardrail + On-Call Debugging (Operational AI)
AI engineering focus: guardrails, graceful degradation, cost predictability, diagnosability.

Deliverables
- DATE-scoped daily spend cap enforced at llm_openai.py boundary
- Mid-run: further LLM calls refuse with COST_BUDGET_EXCEEDED
- Run completes with partial summaries
- Customer UI shows “Summary skipped due to cost cap”
- Debug endpoint shows refusal counts + cost stats

Tooling guidance
- Claude Code: implementation + tests
- Context7: allowed only for verifying OpenAI/API semantics
- MCPs: test runner + failure summary
- Agents: scaffold only (never decide refusal semantics)

### Milestone 3 — Feedback → Controlled Weight Updates (Learning Loop)
AI engineering focus: controlled adaptation, bounded updates, eval deltas, snapshot persistence.

Deliverables
- Aggregate feedback by source
- Compute bounded adjustments (±0.1) with weight bounds (0.5–2.0)
- Persist weight snapshot per cycle
- Run before/after eval comparison artifact
- No regression in grounding/refusal rates

Tooling guidance
- Claude Code: repo helpers + wiring + tests
- MCPs: eval delta summarization
- Skills: fixture expansion or report formatting if repeated
- Agents: allowed for bulk fixture generation (human approves criteria)

### Milestone 4 — Real Users + Per-User Config (Multi-user Reality)
AI engineering focus: isolation, access boundaries, per-user config, auditability.

Deliverables
- users and user_configs tables
- Ranking scoped by user_id
- Feedback scoped by user_id (or prepared for it)
- Minimal auth (magic link or email/password)
- RBAC stub guarding /debug/*

Tooling guidance
- Claude Code: migrations + wiring + tests
- Context7: allowed for auth/OAuth semantics only when needed
- Agents: scaffold auth UI/flows (human approves boundaries)

### Milestone 5 — Email Delivery (Value Delivery)
AI engineering focus: operational delivery, failure handling, audit trail, reuse of artifacts.

Deliverables
- jobs/send_digest --date --user_id
- SMTP integration (SendGrid/Mailgun preferred over OAuth initially)
- Email-safe HTML reuse
- Audit log entries for sends
- Tests for payload correctness

Tooling guidance
- Claude Code: implementation + tests
- Context7: allowed if integrating a specific email SDK
- Hooks: digest built → prepare email payload, send → audit

---

## Backlog (Explicitly De-Prioritized Until Milestones 1–5 Are Green)
- Next.js UI rewrite
- Full OAuth complexity (Gmail OAuth) if SMTP meets requirements
- Redis caching, async ingestion, heavy deploy work
- Broad agentization of runtime

---

## The Throughline
We are learning how to build AI systems that can be:
- trusted by users
- debugged by operators
- improved without regressions
- delivered automatically
- accelerated by AI tools without losing control

That is AI engineering.

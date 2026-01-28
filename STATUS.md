# Project Status — News Digest Engine

## Current Day
**Week 4** — 2026-01-28

## Mode
Execution mode: agent-driven implementation with strict review gates.

## Active Ticket
Ticket 1 — Digest Page Layout Upgrade (Milestone 1)

### PLAN v1 (for Claude)
Objective
- Make `/ui/date/{date}` immediately readable and trustworthy for non-technical users with clear hierarchy, scannable items, and mobile-safe layout; no debug/operator data.

Steps
1. Review current layout in `templates/date.html` and shared styles in `templates/_base.html`.
2. Implement new hierarchy: headline with date + run status, short context line, item list sections, clear spacing.
3. Update CSS for readability and mobile safety (simple CSS, no JS).
4. Ensure summaries/refusals display in a consistent slot per item (placeholder for Ticket 2).
5. Hide evidence text on `/ui/date` for now.
6. Ensure run_id is not shown anywhere in the customer UI.

Files to touch
- `templates/date.html`
- `templates/_base.html` (only if shared styles are needed)

Tests to add/update
- UI smoke test: GET `/ui/date/{date}` returns 200
- HTML contains: page title, item titles, summaries or refusal banners

Done when
- Page is readable without scrolling fatigue
- Non-technical user understands “what happened today” in <10 seconds
- No debug jargon appears
- Tests green

### Acceptance Checklist (human)
- Tests pass locally
- UI clicked manually (happy + refusal case)
- No debug-only fields leak to UI
- Diff reviewed top-to-bottom
- Can explain change in 2 sentences

### Tooling + Agents (this ticket)
- MCPs: repo navigation, test runner, diff summary
- UX Reviewer (advisory subagent): point to `/ui/date/{date}` only; report clarity/trust risks
- Agents: allowed for template scaffolding only

## Next Tickets (order locked)
2) Standardized Refusal Banners
6) Shared UI ↔ Artifact Components (DRY)
3) Citation Rendering + Trust Signals
4) Run Summary Header
5) Email-Safe Digest HTML

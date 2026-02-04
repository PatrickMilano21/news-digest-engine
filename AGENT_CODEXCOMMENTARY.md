# AGENT_CODEXCOMMENTARY.md

Codex review of updated `AGENT_DESIGN.md` + `MEMORY_DESIGN.md`.
Focus: correctness, simplicity, repo alignment, and remaining doc fixes.

---

## Summary

The OpenAI migration is coherent and the layered architecture (advisor.py → advisor_tools.py → repo.py) is clean and testable. The remaining work is mostly implementation detail: enforce tool output truncation and wire the config merge path first.

---

## Decisions Locked

- **Summary cap is $5/day** (update code default to match when implementing).
- **URL-based grounding is the canonical approach** (no normalization required unless you later change direction).

---

## Should Fix

- **Token budgets should be enforced by truncation** — the tool budgets are specified, but advisor_tools must hard‑cap items and truncate fields, not just “target” token size.

---

## Strengths (Keep As‑Is)

- **Blocking Step 0** is explicit and correct (config merge before agent work).
- **Layered tooling** keeps business logic and orchestration clean and testable.
- **OpenAI tool‑calling** fits user‑triggered flows and removes CLI dependency.
- **Server‑side validation** is clear and non‑negotiable.
- **Memory design** is token‑efficient and phased appropriately.

---

## Simplicity Guardrails (v1)

- Max 50 curated items; truncate titles; no raw evidence text.
- No embeddings or compaction in v1 (tag‑based + profiles only).
- Single config merge helper used everywhere ranking occurs.

---

## Repo Alignment Notes

- `run_type` already exists (default `ingest`). Use `advisor` for advisor runs; do not add a new column.
- Add `get_daily_spend_by_type()` and use it in `/debug/costs` (avoid loading all runs in memory).

---

## Overall Assessment

Design is implementation‑ready after one practical clarification (token truncation). Keep v1 simple and enforce the config merge path first.

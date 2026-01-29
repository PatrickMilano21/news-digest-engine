# Project Status — News Digest Engine

**Week 4** — 2026-01-28
**Branch:** `agent/milestone1`

---

## Milestone Status

| Milestone | Description | Status |
|-----------|-------------|--------|
| 1 | UI & HTML Hardening | COMMITTED |
| 2 | Cost Guardrail + On-Call Debugging | COMMITTED |
| 3a | Feedback Reasons (LLM-Suggested, User-Selected) | READY TO COMMIT |
| 3b | Controlled Weight Updates (Learning Loop) | NOT STARTED |

---

## Milestone 3a — Feedback Reasons: COMPLETE

| # | Deliverable | Status |
|---|-------------|--------|
| 1 | LLM suggests 3–5 casual, article-specific tags per item | Done |
| 2 | User can type custom reason OR click suggestions (comma-separated) | Done |
| 3 | Submit button stores reason alongside feedback | Done |
| 4 | UI shows text input + suggested tags as chips | Done |
| 5 | Safe fallback when LLM fails (show "Other" only) | Done |
| 6 | Feedback state persists on page refresh | Done |
| 7 | Submit gated on Useful/Not useful selection | Done |

**Tests:** 245 passing, 17 gated (4 LLM evals, 13 UI smoke)

---

## Milestone 3b — Controlled Weight Updates (Next)

**Deliverables:**
- Aggregate feedback by source (7-day window)
- Compute bounded adjustments (±0.1) with weight bounds (0.5–2.0)
- Persist weight snapshot per cycle
- Run before/after eval comparison artifact
- No regression in grounding/refusal rates

---

# Implementation Reference

## Files Modified

| File | Changes |
|------|---------|
| `src/db.py` | Migrations for `suggested_tags`, `reason_tag` columns |
| `src/clients/llm_openai.py` | `suggest_feedback_tags()`, `_sanitize_tag()` blocklist |
| `src/repo.py` | `get_cached_tags()`, `set_cached_tags()`, `get_all_item_feedback_for_run()` |
| `src/views.py` | `_fetch_or_generate_tags()` for on-demand caching |
| `src/schemas.py` | Added `reason_tag` to `ItemFeedbackRequest` |
| `src/main.py` | Updated `/feedback/item`, `ui_date()` fetches existing feedback |
| `templates/date.html` | Two-step feedback UI with persistence |
| `tests/test_ui_smoke.py` | 13 Playwright browser tests |

## Feedback UX Flow

1. User clicks **Useful** or **Not useful** → stored immediately, button highlights
2. Submit button becomes enabled
3. User types or clicks chips, then **Submit** → reason stored
4. "Why?" section becomes "Thanks for your feedback!"
5. On refresh: buttons show previous selection, reason section hidden if already submitted

## Commands

```bash
make test                                          # 245 pass
make dev                                           # Start server
RUN_UI_SMOKE=1 pytest tests/test_ui_smoke.py -v   # Browser tests
RUN_LLM_EVALS=1 pytest tests/test_feedback_tags.py # LLM evals
```

## SQL Reference

```sql
-- Clear tag cache
UPDATE news_items SET suggested_tags = NULL;

-- View feedback
SELECT item_url, useful, reason_tag, updated_at
FROM item_feedback ORDER BY updated_at DESC LIMIT 10;
```

**Do not commit:** `data/news.db`, `week4.md`, `arch_blueprint.md`

# Project Status — News Digest Engine

**Week 4** — 2026-01-29
**Branch:** `agent/milestone1`

---

## Milestone Status

| Milestone | Description | Status |
|-----------|-------------|--------|
| 1 | UI & HTML Hardening | COMMITTED |
| 2 | Cost Guardrail + On-Call Debugging | COMMITTED |
| 3a | Feedback Reasons (LLM-Suggested, User-Selected) | COMMITTED |
| 3b | Controlled Weight Updates (Learning Loop) | COMPLETE |
| 3c | TF-IDF AI Score (Content Similarity Boost) | PLANNED |

---

## Milestone 3b — Controlled Weight Updates

### Deliverables

| # | Deliverable | Status |
|---|-------------|--------|
| 1 | Aggregate feedback by source (blended 7-day + long-term) | DONE |
| 2 | Compute bounded adjustments (±0.1, bounds 0.5–2.0, min 5 votes) | DONE |
| 3 | Persist weight snapshot per cycle (idempotent) | DONE |
| 4 | Load active weights at runtime (DB → RankConfig) | DONE |
| 5 | Before/after eval comparison artifact | DONE |
| 6 | No regression guard (reject if eval pass rate drops) | DONE |

### Implementation Summary

**Files created:**
- `src/weights.py` — Domain logic (FeedbackStats, compute_effective_rate, compute_weight_adjustments)
- `jobs/update_weights.py` — CLI orchestration (aggregate → compute → eval → snapshot → artifact)
- `tests/test_weights.py` — 21 tests (all passing)

**Files modified:**
- `src/db.py` — Added `weight_snapshots` table
- `src/repo.py` — Added aggregate_feedback_by_source(), get_active_source_weights(), upsert_weight_snapshot()
- `src/main.py` — Updated ui_date(), get_digest(), ui_item() to load dynamic weights
- `jobs/build_digest.py` — Updated to load dynamic weights
- `Makefile` — Added `make weights DATE=YYYY-MM-DD` target

**Test results:** 266 passed, 17 skipped

---

## Design Decisions

| Decision | Choice |
|----------|--------|
| Min votes before adjusting | 5 per source |
| Rate calculation | Blended: `0.7 * rate_7d + 0.3 * rate_longterm` |
| Neutral zone (no change) | effective_rate 0.3–0.7 |
| Adjustment step | ±0.1 per cycle |
| Weight bounds | min 0.5, max 2.0 |
| New source default | 1.0 (RankConfig base) |
| Applied snapshot selection | Latest `applied=1` by `cycle_date` then `created_at` |
| Job idempotency | Re-run for same DATE overwrites previous snapshot |
| RankConfig purity | No DB access; caller loads weights via helper |
| Architecture | Domain logic in `weights.py`, persistence in `repo.py` |
| Snapshot semantics | When `applied=0`, set `weights_after = weights_before` (keeps reads consistent) |
| 7-day window definition | Use `runs.started_at` (UTC), not `news_items.published_at` (aligns with user view time) |
| Idempotency key | `(cycle_date, user_id)` UNIQUE — re-runs are deterministic |
| Per-user future-proofing | `user_id` (nullable) + `config_version` fields added now to avoid breaking migration |

---

## Edge Cases

| Case | Behavior |
|------|----------|
| No feedback in window | `applied=0`, `weights_after = weights_before`, `rejected_reason = "no_feedback"` |
| Source has < 5 votes | Skip adjustment, keep current weight |
| New/unknown source | Default to 1.0, only adjust after threshold met |
| Multiple runs per day | Window uses `runs.started_at` (UTC), deterministic |
| Re-run same DATE | Overwrite existing snapshot by `(cycle_date, user_id)` |
| Eval regression | `applied=0`, `weights_after = weights_before`, `rejected_reason = "regression"` |

---

## Database Schema

```sql
CREATE TABLE IF NOT EXISTS weight_snapshots (
    snapshot_id INTEGER PRIMARY KEY,
    cycle_date TEXT NOT NULL,
    user_id TEXT,
    config_version INTEGER NOT NULL DEFAULT 1,
    weights_before TEXT NOT NULL,
    weights_after TEXT NOT NULL,
    feedback_summary TEXT NOT NULL,
    eval_pass_rate_before REAL,
    eval_pass_rate_after REAL,
    applied INTEGER NOT NULL DEFAULT 0,
    rejected_reason TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(cycle_date, user_id)
);
```

---

## CLI Command

```bash
make weights DATE=2026-01-28
```

---

## Milestone 3c — TF-IDF AI Score (Planned)

Deferred until 3b committed. Content similarity boost using TF-IDF vectors and cosine similarity to positively-labeled historical items.

---

## CODEX Note — 3b Remaining Gaps (FIXED)

1. **Eval guard is stubbed.** — FIXED
   `run_evals_with_weights()` now calls real `evals.runner.run_all()` and returns actual pass_rate.

2. **Weight fixtures missing.** — FIXED
   Added `fixtures/weights/` with:
   - `feedback_mixed.json` — 16 items, 3 sources, varying usefulness rates
   - `feedback_sparse.json` — Sources with < 5 votes (excluded)
   - `feedback_empty.json` — No feedback scenario

3. **Source-weight-specific eval cases.** — FIXED
   Added 2 eval cases to `evals/cases.py`:
   - `source_weight_high_beats_default` — Tests highweight(2.0) > default(1.0) > lowweight(0.5)
   - `source_weight_inverted` — Tests inverted weights

   Supporting changes:
   - Added `fixtures/evals/case_source_weight.xml` — 3 items with different sources
   - Added `use_item_source` param to `parse_rss()` to read per-item `<source>` from XML
   - Updated `EvalCase` dataclass with `use_item_source` field
   - Test count updated: 50 → 52 cases

**Result:** 266 tests passing, eval guard fully wired.

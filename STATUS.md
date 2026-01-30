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
| 3c | TF-IDF AI Score (Content Similarity Boost) | COMPLETE |

---

## Milestone 3c — TF-IDF AI Score (COMPLETE)

**Goal:** Add a deterministic, low-cost content-similarity signal on top of base score.

**Formula:** `final_score = base_score + (alpha * ai_score)`

### Deliverables

| # | Deliverable | Status |
|---|-------------|--------|
| 1 | Define preference labels from feedback signals | DONE |
| 2 | Build TF-IDF vectors from item content | DONE |
| 3 | Compute cosine similarity to positive history | DONE |
| 4 | Add `ai_score` as bounded additive boost | DONE |
| 5 | Cold-start fallback (`ai_score = 0`) | DONE |
| 6 | Evals/fixtures to validate behavior | DONE |

---

## Implementation Summary

### Design Decisions

| Decision | Value | Rationale |
|----------|-------|-----------|
| Text field | `title + evidence` | No summary column in DB |
| Alpha | 0.1 (max 0.2) | Nudge only, avoid AI score dominating |
| Corpus | All historical items | Richer vocabulary for TF-IDF fit |
| Similarity target | Positives only | Compare against thumbs-up items |

### Files Created/Modified

| File | Change |
|------|--------|
| `src/ai_score.py` | NEW — TF-IDF vectorizer + cosine similarity (pure domain logic) |
| `src/scoring.py` | Added `ai_score_alpha` to RankConfig (with bounds validation); updated `rank_items()` to accept `ai_scores` dict |
| `src/repo.py` | Added `get_positive_feedback_items()` and `get_all_historical_items()` |
| `src/views.py` | Updated `build_ranked_display_items()` to accept `ai_scores` param |
| `src/main.py` | Added ai_score computation in `rank_for_date()`, `get_digest()`, and `ui_date()` |
| `jobs/build_digest.py` | Added ai_score computation before `rank_items()` |
| `jobs/daily_run.py` | Added ai_score computation + source weights load before `rank_items()` |
| `tests/test_ai_score.py` | NEW — 11 tests (similarity, cold start, bounds, duplicates, ranking integration) |
| `fixtures/ai_score/` | NEW — 4 JSON fixtures |
| `pyproject.toml` | Added `scikit-learn>=1.4` dependency |

### Fixtures

| Fixture | Purpose |
|---------|---------|
| `positive_history.json` | 3 thumbs-up items with AI/ML terms |
| `new_similar_item.json` | Should get boost (AI startup article) |
| `new_unrelated_item.json` | Should NOT get boost (BBQ recipes) |
| `duplicate_item.json` | Same URL as positive → ai_score = 0 |

### How It Works

```
User thumbs-up → item_feedback table
                        ↓
get_positive_feedback_items() → positives list
                        ↓
get_all_historical_items() → corpus list
                        ↓
build_tfidf_model(corpus) → TF-IDF model
                        ↓
compute_ai_scores(model, positives, new_items) → {url: score}
                        ↓
rank_items(..., ai_scores=ai_scores)
                        ↓
final_score = base_score + (0.1 * ai_score)
```

### Test Results

```
277 passed, 17 skipped
52 eval cases (no regression)
```

---

## Deferred (v2)

- ScoreBreakdown: add ai_score field for explainability ("why this rank")
- MCP eval-delta summary step
- Scoring Integrity Reviewer subagent

---

## Done When (All Met)

- [x] `make test` passes (277 passed)
- [x] `ai_score` is deterministic and bounded [0, 1]
- [x] `ai_score_alpha` validated [0.0, 0.2]
- [x] Ranking evals show no regression (52 cases)
- [x] New fixtures prove similarity boost works
- [x] All call sites use ai_scores (main.py, views.py, build_digest.py, daily_run.py)
- [x] All call sites use dynamic source weights

# Run History
Append-only log of agent runs.

---

<!-- Agent appends entries below this line -->

## Run #4 - 2026-01-31

**Branch:** agent/milestone1
**Trigger:** Overnight review

### Issues Found: 1 (down from 4)
1. **Medium - API isolation:** `/digest/{date_str}` line 400 - `get_run_by_day()` missing user_id

### Fixed Since Run #3
- ✅ **Critical:** `aggregate_feedback_by_source()` now has `user_id` parameter (repo.py:1023)
- ✅ **API:** `/rank/{date_str}` line 365 now passes `user_id` to `get_positive_feedback_items()`
- ✅ **API:** `/digest/{date_str}` lines 408, 414 now pass `user_id` to scoring calls

### Clean Areas Verified
- scoring.py: Formulas correct, division guards present ✓
- weights.py: Effective rate formula matches docstring, bounds enforced ✓
- ai_score.py: Similarity bounded [0,1], duplicate detection, cold start ✓
- Jobs: `update_weights.py:182` passes `user_id` to `aggregate_feedback_by_source()` ✓
- UI routes: `/ui/date/{date_str}` fully scoped (lines 450-458) ✓

---

## Run #3 - 2026-01-31

**Branch:** agent/milestone1
**Trigger:** Overnight review

### Issues Found (unchanged)
1. **Critical - User isolation:** `aggregate_feedback_by_source()` missing user_id (repo.py:1017-1082)
2. **API isolation:** `/rank/{date_str}` missing user_id on `get_positive_feedback_items()` (main.py:360)
3. **API isolation:** `/digest/{date_str}` missing user_id on scoring calls (main.py:400,406)
4. **Low risk:** Pydantic bounds validation (acceptable)

### Clean Areas Verified
- scoring.py: Formulas correct, division guards present ✓
- weights.py: Effective rate formula matches docstring, bounds enforced ✓
- ai_score.py: Similarity bounded [0,1], duplicate detection, cold start ✓
- UI routes: `/ui/date/{date_str}` properly scopes to user ✓
- Jobs: `build_digest.py`, `daily_run.py` pass user_id correctly ✓

### Changes Since Run #2
- No code changes detected in scoring files
- All issues remain unfixed

---

## Run #2 - 2026-01-31

**Branch:** agent/milestone1
**Trigger:** Overnight review

### Issues Found
1. **Critical - User isolation:** `aggregate_feedback_by_source()` missing user_id parameter (unchanged)
2. **API isolation:** `/rank/{date_str}` missing user_id on `get_positive_feedback_items()`
3. **API isolation:** `/digest/{date_str}` missing user_id on `get_active_source_weights()` and `get_positive_feedback_items()`
4. **Low risk:** Pydantic bounds validation (acceptable, no runtime assertion needed)

### Clean Areas Verified
- scoring.py: All formulas correct, division guards present ✓
- weights.py: Effective rate formula matches docstring, bounds enforced ✓
- ai_score.py: Similarity bounded [0,1], duplicate detection, cold start handled ✓
- UI routes: `/ui/date/{date_str}` properly scopes to user ✓
- Jobs: `build_digest.py`, `daily_run.py` pass user_id correctly ✓

### Changes Since Run #1
- Identified 2 additional API route isolation issues (previously overlooked)
- Core scoring logic unchanged and correct

---

## Run #1 - 2026-01-30

**Branch:** agent/milestone1
**Commit:** 2ff0926 (Milestone 3c TF-IDF ai_score + Week4 update)

### Issues Found
1. **Critical - User isolation:** `aggregate_feedback_by_source()` missing user_id parameter
2. **Low risk - Bounds validation:** `rank_items()` relies on Pydantic validator for ai_score_alpha bounds
3. **Defensive - Missing guard:** `compute_ai_scores()` implicit empty list handling

### Clean Areas Verified
- scoring.py: score_item(), compute_score_breakdown(), rank_items()
- weights.py: compute_effective_rate(), compute_weight_adjustments()
- ai_score.py: compute_ai_scores(), build_tfidf_model()
- User isolation in build_digest.py, daily_run.py (weight/feedback queries)

### Human Overrides Applied
None (no human overrides defined yet)

### False Positives
None identified

### Learnings
- TF-IDF corpus intentionally global (richer vocabulary) while positive items user-scoped
- Pydantic validators provide config-time bounds but no runtime enforcement
- Python list comprehension `[0.0] * 0` safely returns `[]`

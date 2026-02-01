# Learned Patterns
Last updated: 2026-01-31 (Run #4)

## Safe Patterns (Don't Flag)

### Calculation formulas
- `(1.0 + relevance) * source_weight * recency_decay` - Base score formula (scoring.py:96)
- `1.0 / (1.0 + (age_hours / half_life))` - Recency decay with safe denominator (scoring.py:75)
- `0.7 * rate_7d + 0.3 * rate_longterm` - Effective rate blend (weights.py:40)

### Guards that work
- `if half_life <= 0.0: half_life = 24.0` - Division by zero prevention (scoring.py:72-73)
- `max(0.0, min(1.0, score))` - Bounds clamping for ai_score (ai_score.py:119)
- Pydantic Field validators: `ge=0.0, le=0.2` for ai_score_alpha (scoring.py:37)

### Intentional design
- Empty corpus returns None model (ai_score.py:29-30) - Cold start handling
- Duplicate URLs get 0.0 ai_score (ai_score.py:95-97) - Self-boost prevention
- TF-IDF corpus from all items (global) - Richer vocabulary than user-only subset
- UI routes (`/ui/*`) properly use `get_current_user()` and pass `user_id`
- `aggregate_feedback_by_source()` now has `user_id` param (repo.py:1023) ✓
- `/rank/{date_str}` passes `user_id` to scoring calls (main.py:365) ✓
- `/digest/{date_str}` passes `user_id` to scoring calls (main.py:408,414) ✓

## Risky Patterns (Always Flag)

- API routes calling `get_run_by_day()` without `user_id` - Returns wrong user's run
- Score calculation without bounds checking
- Weight adjustment ignoring min/max bounds

## Uncertain (Watching)

- Implicit Python safety (`[0.0] * len([])` returns `[]`) - Safe but implicit

## Statistics
- Total runs: 4
- Issues found: 1 (down from 4)
- Fixed in Run #4: 3 issues
- False positive rate: 0%

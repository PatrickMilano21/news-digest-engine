# Learned Patterns
Last updated: 2026-01-31 (Run #4)

## Safe Patterns (Don't Flag)
- `suggest_feedback_tags()` exempt from daily cap - Intentional design (cheap call, separate concern)
- Cache hit path skipping `summarize()` - Cost tracked via saved_cost_usd, not a gap
- Single retry attempt for malformed JSON - Bounded at 2 API calls max per item
- API key from env var (`OPENAI_API_KEY`) - Standard secure practice
- Jobs iterating over `top_n` or `TOP_N` - Bounded iteration, not unbounded
- Per-item try/except in pipeline - Isolation pattern, continues on error
- `daily_run.py:290` - Passes `day=day` ✓
- `build_digest.py:101` - Passes `day=day` ✓ (FIXED in Run #4)

## Risky Patterns (Always Flag)
- `summarize()` called without `day=` parameter - Budget cap not enforced (CRITICAL)
- Missing timeout on `urllib.request.urlopen()` - Risk of hanging indefinitely
- Unbounded loop calling LLM API - Cost explosion risk
- Hardcoded API keys in source code - Security violation

## Uncertain (Watching)
- No explicit rate limit (429) retry logic - Currently caught as generic `LLM_API_FAIL`, may need backoff
- Cost estimates vs actual OpenAI pricing - Rates hardcoded, may drift over time
- Tag suggestion not tracking to run stats - Separate from main cost tracking, may need visibility

## Statistics
- Total runs: 4
- Issues found: 0 🎉
- Fixed in Run #4: `build_digest.py:101` now passes `day=day`
- False positive rate: 0% (all findings valid)

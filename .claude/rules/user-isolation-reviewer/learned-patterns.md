# Learned Patterns
Last updated: 2026-01-31 (Run #5)

## Safe Patterns (Don't Flag)
- `news_items` table - Intentionally global (deduplication)
- `summary_cache` table - Same evidence = same summary
- `/ingest/raw` endpoint - Admin/system operation
- `/ui/config`, `/ui/settings` - Placeholder pages with no user data
- `get_all_historical_items()` - TF-IDF corpus is global (vocabulary building)
- `daily_run.py` idempotency check - Initial check uses global, then runs per-user
- Debug routes (`/debug/*`) - Admin-only, no user-scoping needed
- `/runs/latest` - Now properly scoped (Run #5)
- `/rank/{date_str}` - Now properly scoped (Run #5)
- `/feedback/run`, `/feedback/item` - Now properly scoped (Run #5)
- `build_digest.py` - Now properly passes user_id (Run #5)

## Risky Patterns (Always Flag)
- API routes without `get_current_user()` when returning user-specific data
- Feedback endpoints not passing `user_id` to upsert functions
- Routes using `get_run_by_day()`, `get_latest_run()` without `user_id`
- Routes calling `get_positive_feedback_items()` without `user_id`
- Routes calling `get_active_source_weights()` without `user_id`

## Uncertain (Watching)
- `get_all_historical_items()` - May need user-scoping if items become user-specific
- `/digest/{date_str}` line 400 - `get_run_by_day()` without user_id (partial fix pending)

## Statistics
- Total runs: 5
- Issues found (latest): 1 (down from 6 in Run #4)
- Fixed since Run #4: 5 issues (4 API routes + 1 job)
- False positive rate: N/A

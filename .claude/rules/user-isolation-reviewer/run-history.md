# Run History
Append-only log of agent runs.

---

<!-- Agent appends entries below this line -->

### 2026-01-31 Run #5 | Branch: agent/milestone1
- **Issues found:** 1 (down from 6)
- **Files scanned:** main.py, repo.py, views.py, daily_run.py, build_digest.py, update_weights.py, auth.py
- **Summary:** Overnight review. Major progress - 5 issues fixed since Run #4. Remaining issue: `/digest/{date_str}` line 400 calls `get_run_by_day()` without user_id (other calls in same route properly scoped). Fixed: `/runs/latest`, `/rank/{date_str}`, `/feedback/run`, `/feedback/item` now properly call `get_current_user()` and pass `user_id`. Fixed: `build_digest.py` now passes `user_id` to `get_run_by_day()`. All UI routes, debug routes, jobs properly scoped.

### 2026-01-31 Run #4 | Branch: agent/milestone1
- **Issues found:** 6
- **Files scanned:** main.py, repo.py, views.py, daily_run.py, build_digest.py, update_weights.py, auth.py
- **Summary:** Overnight review. Same 6 issues as Run #3: 5 API routes missing user isolation (`/runs/latest`, `/rank/{date_str}`, `/digest/{date_str}`, `/feedback/run`, `/feedback/item`) + 1 job issue (`build_digest.py` line 53 missing user_id on `get_run_by_day()`). All UI routes, debug routes properly scoped. No changes detected since last run.

### 2026-01-31 Run #3 | Branch: agent/milestone1
- **Issues found:** 6
- **Files scanned:** main.py, repo.py, views.py, daily_run.py, build_digest.py, update_weights.py, auth.py
- **Summary:** Overnight review. Same 6 issues as Run #2: 5 API routes missing user isolation (`/runs/latest`, `/rank/{date_str}`, `/digest/{date_str}`, `/feedback/run`, `/feedback/item`) + 1 job issue (`build_digest.py` line 53 missing user_id on `get_run_by_day()`). All UI routes, debug routes properly scoped. `daily_run.py` and `update_weights.py` properly accept and use `--user-id`.

### 2026-01-30 Run #2 | Branch: agent/milestone1
- **Issues found:** 6
- **Files scanned:** main.py, repo.py, views.py, daily_run.py, build_digest.py, update_weights.py, auth.py
- **Summary:** Re-review. Found 5 API routes missing user isolation: `/runs/latest`, `/rank/{date_str}`, `/digest/{date_str}`, `/feedback/run`, `/feedback/item`. Found 1 job issue: `build_digest.py` missing user_id on `get_run_by_day()`. All UI routes, debug routes properly scoped. `daily_run.py` and `update_weights.py` properly accept and use `--user-id`.

### 2026-01-30 | Branch: agent/milestone1
- **Issues found:** 5
- **Files scanned:** main.py, repo.py, views.py, daily_run.py, build_digest.py, update_weights.py, auth.py
- **Summary:** Initial review. Found 5 API routes missing user isolation: `/runs/latest`, `/rank/{date_str}`, `/digest/{date_str}`, `/feedback/run`, `/feedback/item`. All UI routes, debug routes, and jobs properly scoped.

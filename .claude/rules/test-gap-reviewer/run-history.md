# Run History
Append-only log of agent runs.

---

<!-- Agent appends entries below this line -->

### Run #5 - 2026-01-31
- **Branch:** agent/milestone1
- **Trigger:** Overnight review
- **Routes scanned:** 23
- **Source files scanned:** 31
- **Test files scanned:** 44
- **Issues found:** 11 (unchanged)
  - Routes without tests: 2 (unchanged)
  - Functions without tests: 6 (unchanged)
  - Jobs without tests: 1 (partial)
  - Error paths without tests: 2 (unchanged)
- **Key findings:**
  - No new routes, functions, or tests since Run #4
  - Remaining issues are stable, low priority (admin-only or integration-tested)
  - Auth error paths (409 HTTP, NULL password_hash) still untested at endpoint level
- **Corrections:** None

### Run #4 - 2026-01-31
- **Branch:** agent/milestone1
- **Trigger:** Overnight review
- **Routes scanned:** 23
- **Source files scanned:** 31
- **Test files scanned:** 44
- **Issues found:** 11 (down from 12)
  - Routes without tests: 2 (unchanged)
  - Functions without tests: 6 (unchanged)
  - Jobs without tests: 1 (partial)
  - Error paths without tests: 2 (down from 3)
- **Key findings:**
  - `rss_fetch.py` non-200 path verified tested (was false positive)
  - No new routes or public functions since Run #3
  - Auth error paths (409 HTTP, NULL password_hash) still untested at endpoint level
- **Corrections:** Removed `rss_fetch.py` from error paths (found `test_fetch_rss_non_200_raises`)

### Run #3 - 2026-01-31
- **Branch:** agent/milestone1
- **Trigger:** Overnight review
- **Routes scanned:** 26
- **Source files scanned:** 31
- **Test files scanned:** 44
- **Issues found:** 12
  - Routes without tests: 2 (down from 3)
  - Functions without tests: 6
  - Jobs without tests: 1 (partial)
  - Error paths without tests: 3
- **Key findings:**
  - `/debug/costs` now has test coverage in `test_cost_cap.py:TestDebugCostsEndpoint`
  - Views public functions still lack direct unit tests (acceptable - integration tested)
  - Auth error paths (409 HTTP, NULL password_hash) still untested at endpoint level
- **Corrections:** Found new test coverage for `/debug/costs`

### Run #2 - 2026-01-30
- **Branch:** agent/milestone1
- **Trigger:** Manual review request
- **Routes scanned:** 24
- **Source files scanned:** 27
- **Test files scanned:** 44
- **Issues found:** 13
  - Routes without tests: 3
  - Functions without tests: 6
  - Jobs without tests: 1 (partial)
  - Error paths without tests: 3
- **Key findings:**
  - `/debug/costs` route still lacks test coverage
  - `views.py` public functions lack direct unit tests (acceptable - tested via integration)
  - Auth error paths (409 HTTP, NULL password_hash) untested at endpoint level
- **Corrections:** Fixed `/ui/settings` (found in `test_ui_smoke.py`)

### Run #1 - 2026-01-30
- **Branch:** agent/milestone1
- **Trigger:** Manual review request
- **Routes scanned:** 24
- **Source files scanned:** 27
- **Test files scanned:** 44
- **Issues found:** 14
  - Routes without tests: 4
  - Functions without tests: 6
  - Jobs without tests: 1 (partial)
  - Error paths without tests: 3
- **Key findings:**
  - `/ui/settings` route has no test coverage (FALSE POSITIVE - in smoke tests)
  - `/debug/costs` route has no test coverage
  - `views.py` public functions lack direct unit tests
  - Auth error paths (409, NULL password_hash) untested

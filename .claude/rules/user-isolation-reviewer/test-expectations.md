# Second Run Test Expectations
Created: 2026-01-30

## Pre-Run State (Run #1)
- **agent-findings.md**: 5 issues, dated 2026-01-30
- **learned-patterns.md**: 25 lines, Total runs: 1, Issues found: 5
- **run-history.md**: 1 entry (2026-01-30)
- **human-overrides.md**: Empty (no overrides added)

## Expected Behavior on Run #2

### agent-findings.md
- [x] Section replaced (not appended) ✅
- [x] Timestamp updated to "Run #2" ✅
- Note: Found 6 issues (1 more than run #1 - deeper scan caught `build_digest.py`)

### learned-patterns.md
- [x] Statistics updated: Total runs: 2 ✅
- [x] Issues found count updated (now shows 6) ✅
- [x] Stays under 50 lines (26 lines) ✅
- [x] Added new safe pattern: `daily_run.py idempotency check` ✅

### run-history.md
- [x] New entry appended (run #2) ✅
- [x] Now has 2 entries total ✅
- [x] First entry preserved ✅

### human-overrides.md
- [x] Unchanged (agent never writes here) ✅

## Verification Results
**All expectations met.** Run #2 completed 2026-01-30.

### Interesting Finding
Run #2 found 6 issues vs Run #1's 5 issues. The agent caught an additional issue in `build_digest.py:main()` calling `get_run_by_day()` without `user_id`. This demonstrates:
- Agent can become more thorough across runs
- Findings are replaced, not accumulated (fresh scan each time)
- Learning patterns help agent refine what to check

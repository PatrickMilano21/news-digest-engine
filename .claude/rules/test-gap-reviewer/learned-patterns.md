# Learned Patterns
Last updated: 2026-01-31 (Run #5)

## Safe Patterns (Don't Flag)
- Helper functions tested via parent (e.g., `render_header()` via `render_digest_html()`)
- Private functions (`_fetch_cached_summary()`, `_fetch_or_generate_tags()`) - tested via callers
- Config/constants files (`ui_constants.py`, `error_codes.py`) - no logic to test
- Placeholder pages (`/ui/config`, `/ui/settings`) - minimal logic, template-only
- Smoke tests count as coverage (e.g., `test_ui_smoke.py`)
- Debug routes in dedicated test classes (e.g., `TestDebugCostsEndpoint`)
- `fetch_rss()` non-200 path - tested via `test_fetch_rss_non_200_raises()`

## Risky Patterns (Always Flag)
- New API routes without corresponding test_*.py coverage
- Public view helpers without unit tests (e.g., `build_*` functions in views.py)
- Debug routes that bypass normal error handling
- Error code paths (4xx, 5xx responses) without negative test cases
- HTTP-level error responses (e.g., 409 duplicate) tested only at repo layer

## Uncertain (Watching)
- Jobs tested only via repo functions (may miss orchestration bugs)
- LLM-related functions that require API mocking - complex test setup
- View builder functions tested only via integration tests (adequate for now)

## Statistics
- Total runs: 5
- Issues found: 11 (stable since run #4)
- False positive rate: 2/14 (14%) - `/ui/settings` in smoke, `rss_fetch` non-200 tested

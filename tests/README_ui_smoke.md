# UI_Testing.md

## Purpose
Define a repeatable, scalable approach to UI testing as the product expands, with an agent that performs deterministic UI checks using Playwright (local) or Browserbase (remote).

## Principles
- Prefer deterministic checks over subjective review.
- One agent, many surfaces: scope per invocation.
- Fail fast on missing elements or incorrect redirects.
- Do not rely on templates alone; test rendered pages.

## When to Run
- After any UI change (new page or material layout change).
- Before merge on UI-related tickets.
- After refactors that touch routing or templates.

## Agent: UI Smoke Tester
**Goal:** Validate that key customer UI routes render and contain expected elements.

**Inputs (required):**
- Base URL (e.g., http://localhost:8001)
- Target routes (e.g., /, /ui/date/{date}, /ui/history, /ui/config, /ui/settings)
- Expected selectors/text per route

**Tools:**
- Playwright MCP (local)
- Browserbase MCP (remote, optional)

**Output:**
- Pass/fail per route
- Missing selectors or unexpected content
- Screenshot on failure (if available)

**Forbidden:**
- Code edits
- Debug/operator routes
- Subjective UX judgments (handled by UX Reviewer)

## Suggested Checks (Current Customer UI)
- `/` redirects to most recent available date
- `/ui/date/{date}` renders:
  - Page title
  - Item titles
  - Summary or refusal banner
  - Feedback controls
- `/ui/history` renders list of dates + ratings
- `/ui/config` loads (placeholder ok)
- `/ui/settings` loads (placeholder ok)
- No debug fields (run_id, error codes) visible on customer pages

## Expansion Strategy
As UI grows:
- Add new routes to the UI smoke checklist.
- Add selectors for new UI components.
- Keep selectors stable by using data-testid or clear class names.
- Maintain a small set of high-signal checks rather than exhaustive UI diffing.

## Browserbase vs Playwright
- Use Playwright for local dev checks (fast, cheap).
- Use Browserbase for CI-like checks or remote rendering parity.

---

## Implementation: `tests/test_ui_smoke.py`

**Status:** 13/13 tests passing

### Setup
```bash
# Install Playwright (one-time)
pip install playwright && playwright install chromium

# Start dev server
make dev

# Run UI smoke tests (in another terminal)
RUN_UI_SMOKE=1 pytest tests/test_ui_smoke.py -v

# With Browserbase (cloud)
RUN_UI_SMOKE=1 BROWSERBASE_API_KEY=xxx pytest tests/test_ui_smoke.py -v
```

### Test Coverage

| Test Class | Test | What It Checks |
|------------|------|----------------|
| `TestHomeRedirect` | `test_home_redirects_to_date` | `/` redirects to `/ui/date/{date}` |
| `TestDatePage` | `test_page_title_present` | h1 contains "News Digest" |
| `TestDatePage` | `test_item_titles_render` | `.item` cards with `.item-title` visible |
| `TestDatePage` | `test_feedback_controls_present` | `.feedback-btn` and `.feedback-reason-input` visible |
| `TestDatePage` | `test_no_debug_fields_visible` | No `run_id`, `error_code`, `request_id` in visible text |
| `TestHistoryPage` | `test_history_loads` | h1 contains "History" |
| `TestHistoryPage` | `test_history_shows_dates` | Date links or empty message |
| `TestConfigPage` | `test_config_loads` | Page loads without error |
| `TestSettingsPage` | `test_settings_loads` | Page loads without error |
| `TestNavigation` | `test_hamburger_menu_opens` | `.menu-btn` click shows `.left-nav` |
| `TestNavigation` | `test_nav_links_work` | Date links navigate correctly |
| `TestFeedbackInteraction` | `test_click_suggestion_fills_input` | `.feedback-tag` click fills `.feedback-reason-input` |
| `TestFeedbackInteraction` | `test_submit_feedback_shows_confirmation` | `.feedback-btn` click adds `active-up` class |

### Key Patterns

**Gating tests (skip by default):**
```python
ui_smoke = pytest.mark.skipif(
    not os.environ.get("RUN_UI_SMOKE"),
    reason="UI smoke tests skipped by default."
)
```

**Browserbase vs local detection:**
```python
browserbase_key = os.environ.get("BROWSERBASE_API_KEY")
if browserbase_key:
    browser = p.chromium.connect_over_cdp(f"wss://connect.browserbase.com?apiKey={browserbase_key}")
else:
    browser = p.chromium.launch(headless=True)
```

**Checking visible text only (not script tags):**
```python
# Use inner_text to get visible content only
visible_text = page.inner_text("body").lower()
assert "run_id" not in visible_text, "run_id visible to customer"
```

**Partial class matching with regex:**
```python
# Element has class="feedback-btn active-up", use regex to match
expect(useful_btn).to_have_class(re.compile(r"active-up"))
```

### Selectors Used
- `.item` — Article card container
- `.item-title` — Article title
- `.feedback` — Feedback section
- `.feedback-btn` — Useful/Not useful buttons
- `.feedback-reason-input` — Text input for reason
- `.feedback-tag` — Suggestion chip
- `.menu-btn` — Hamburger menu button
- `.left-nav` — Navigation panel

---

## Future Enhancements
- Add a snapshot mode for visual diffs (optional).
- Add CI job to run smoke agent on PRs.
- Store smoke results as artifacts for audit.


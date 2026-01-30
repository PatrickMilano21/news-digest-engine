"""
UI Smoke Tests - Browser-based UI validation using Playwright.

Run locally: RUN_UI_SMOKE=1 pytest tests/test_ui_smoke.py -v
Run with Browserbase: RUN_UI_SMOKE=1 BROWSERBASE_API_KEY=xxx pytest tests/test_ui_smoke.py -v

Based on UI_Testing.md spec from Codex.
"""
import os
import re
import pytest

# Gate these tests - they require a running server + browser
ui_smoke = pytest.mark.skipif(
    not os.environ.get("RUN_UI_SMOKE"),
    reason="UI smoke tests skipped by default. Set RUN_UI_SMOKE=1 and start dev server first."
)

# Check if playwright is available
try:
    from playwright.sync_api import sync_playwright, expect
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


BASE_URL = os.environ.get("UI_SMOKE_BASE_URL", "http://localhost:8001")


@pytest.fixture(scope="module")
def browser():
    """Create browser instance - uses Browserbase if configured, else local."""
    if not PLAYWRIGHT_AVAILABLE:
        pytest.skip("Playwright not installed. Run: pip install playwright && playwright install")

    browserbase_key = os.environ.get("BROWSERBASE_API_KEY")

    with sync_playwright() as p:
        if browserbase_key:
            # Connect to Browserbase (cloud)
            # Note: Adjust endpoint based on Browserbase docs
            browser = p.chromium.connect_over_cdp(
                f"wss://connect.browserbase.com?apiKey={browserbase_key}"
            )
        else:
            # Local browser
            browser = p.chromium.launch(headless=True)

        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    """Create a new page for each test."""
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()


# --- Smoke Tests per Codex Spec ---

@ui_smoke
class TestHomeRedirect:
    """Test / redirects to most recent date."""

    def test_home_redirects_to_date(self, page):
        """Home should redirect to /ui/date/{date}."""
        page.goto(BASE_URL)

        # Should redirect to a date page or show welcome
        url = page.url
        assert "/ui/date/" in url or "Welcome" in page.content(), \
            f"Expected redirect to date page or welcome, got: {url}"


@ui_smoke
class TestDatePage:
    """Test /ui/date/{date} renders correctly."""

    def test_page_title_present(self, page):
        """Date page should have title."""
        page.goto(f"{BASE_URL}/ui/date/2026-01-28")

        # Check for page header
        header = page.locator("h1")
        expect(header).to_contain_text("News Digest")

    def test_item_titles_render(self, page):
        """Date page should show article titles."""
        page.goto(f"{BASE_URL}/ui/date/2026-01-28")

        # Check for item cards
        items = page.locator(".item")
        # Should have at least one item (or empty state)
        count = items.count()
        if count == 0:
            # Check for empty state
            assert "No stories found" in page.content() or "empty" in page.content().lower()
        else:
            # Check first item has a title
            first_title = page.locator(".item-title").first
            expect(first_title).to_be_visible()

    def test_feedback_controls_present(self, page):
        """Date page should have feedback controls."""
        page.goto(f"{BASE_URL}/ui/date/2026-01-28")

        # Check for feedback elements
        feedback = page.locator(".feedback")
        if feedback.count() > 0:
            # Should have useful/not useful buttons
            expect(page.locator(".feedback-btn").first).to_be_visible()
            # Should have reason input
            expect(page.locator(".feedback-reason-input").first).to_be_visible()

    def test_no_debug_fields_visible(self, page):
        """Customer page should not expose debug data in visible text."""
        page.goto(f"{BASE_URL}/ui/date/2026-01-28")

        # Get visible text only (excludes script/style content)
        visible_text = page.inner_text("body").lower()
        # These debug fields should NOT be visible to the user
        # Note: run_id may exist in script tags for functional purposes, but not in visible text
        assert "run_id" not in visible_text, "run_id visible to customer"
        assert "error_code" not in visible_text, "error_code visible to customer"
        assert "request_id" not in visible_text, "request_id visible to customer"


@ui_smoke
class TestHistoryPage:
    """Test /ui/history renders correctly."""

    def test_history_loads(self, page):
        """History page should load."""
        page.goto(f"{BASE_URL}/ui/history")

        expect(page.locator("h1")).to_contain_text("History")

    def test_history_shows_dates(self, page):
        """History page should list dates."""
        page.goto(f"{BASE_URL}/ui/history")

        # Should have date links or empty message
        content = page.content()
        assert "/ui/date/" in content or "No digests" in content


@ui_smoke
class TestConfigPage:
    """Test /ui/config renders correctly."""

    def test_config_loads(self, page):
        """Config page should load (placeholder ok)."""
        page.goto(f"{BASE_URL}/ui/config")

        assert page.locator("h1").count() > 0 or "Config" in page.content()


@ui_smoke
class TestSettingsPage:
    """Test /ui/settings renders correctly."""

    def test_settings_loads(self, page):
        """Settings page should load (placeholder ok)."""
        page.goto(f"{BASE_URL}/ui/settings")

        assert page.locator("h1").count() > 0 or "Settings" in page.content()


@ui_smoke
class TestNavigation:
    """Test navigation elements work."""

    def test_hamburger_menu_opens(self, page):
        """Hamburger menu should open nav panel."""
        page.goto(f"{BASE_URL}/ui/date/2026-01-28")

        # Find and click hamburger
        menu_btns = page.locator(".menu-btn")
        if menu_btns.count() > 0:
            menu_btns.first.click()

            # Nav should be visible
            nav = page.locator(".left-nav")
            expect(nav).to_be_visible()

    def test_nav_links_work(self, page):
        """Nav links should navigate to correct pages."""
        page.goto(f"{BASE_URL}/ui/history")

        # Click on a date link if present
        date_links = page.locator("a[href*='/ui/date/']")
        if date_links.count() > 0:
            date_links.first.click()
            assert "/ui/date/" in page.url


@ui_smoke
class TestFeedbackInteraction:
    """Test feedback flow works end-to-end."""

    def test_click_suggestion_fills_input(self, page):
        """Clicking a suggestion chip should fill the input."""
        page.goto(f"{BASE_URL}/ui/date/2026-01-28")

        # Find a suggestion chip
        chips = page.locator(".feedback-tag")
        if chips.count() > 0:
            chip_text = chips.first.text_content()
            chips.first.click()

            # Input should contain the chip text
            input_field = page.locator(".feedback-reason-input").first
            expect(input_field).to_have_value(chip_text.strip())

    def test_submit_feedback_shows_confirmation(self, page):
        """Submitting feedback should show confirmation."""
        page.goto(f"{BASE_URL}/ui/date/2026-01-28")

        # Click useful button
        useful_btns = page.locator(".feedback-btn[data-useful='true']")
        if useful_btns.count() > 0:
            useful_btn = useful_btns.first
            useful_btn.click()

            # Button should get active class (regex since element has multiple classes)
            expect(useful_btn).to_have_class(re.compile(r"active-up"))

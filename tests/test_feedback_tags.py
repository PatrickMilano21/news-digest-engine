"""Tests for feedback tags feature (Milestone 3a)."""
import json
import os
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest
from dotenv import load_dotenv

# Load .env for API keys (needed for eval tests)
load_dotenv()

from src.db import get_conn, init_db
from src.schemas import NewsItem
from src.repo import (
    insert_news_items,
    get_cached_tags,
    set_cached_tags,
    upsert_item_feedback,
    get_item_feedback,
    start_run,
    finish_run_ok,
)
# Import after dotenv load so API key is available
from src.clients.llm_openai import suggest_feedback_tags


# Mark for LLM eval tests (run with: pytest -m llm_eval --run-llm-evals)
llm_eval = pytest.mark.skipif(
    not os.environ.get("RUN_LLM_EVALS"),
    reason="LLM eval tests skipped by default. Set RUN_LLM_EVALS=1 to run."
)


@pytest.fixture
def db_conn(tmp_path, monkeypatch):
    """Create a temp database for testing."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))
    conn = get_conn()
    init_db(conn)
    yield conn
    conn.close()


@pytest.fixture
def sample_item():
    """Create a sample news item for testing."""
    return NewsItem(
        source="TestSource",
        url="https://example.com/article",
        published_at=datetime.now(timezone.utc),
        title="Test Article Title",
        evidence="Some evidence text",
    )


class TestSuggestFeedbackTags:
    """Tests for suggest_feedback_tags function."""

    def test_returns_list_on_success(self, monkeypatch, sample_item):
        """Should return a list of tags on successful LLM call."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        mock_response = json.dumps(["Relevant topic", "Good source", "Clear writing"])

        with patch("src.clients.llm_openai.urllib.request.urlopen") as mock_urlopen:
            mock_body = MagicMock()
            mock_body.read.return_value = json.dumps({
                "choices": [{"message": {"content": mock_response}}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 20}
            }).encode()
            mock_urlopen.return_value.__enter__.return_value = mock_body

            tags = suggest_feedback_tags(sample_item)

        assert isinstance(tags, list)
        assert len(tags) >= 1
        assert len(tags) <= 5

    def test_prompt_includes_article_title_and_source(self, monkeypatch):
        """Prompt sent to LLM should include article title and source for context."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        item = NewsItem(
            source="TechCrunch",
            url="https://techcrunch.com/ai-article",
            published_at=datetime.now(timezone.utc),
            title="OpenAI Releases GPT-5 with Major Improvements",
            evidence="Some evidence",
        )

        captured_payload = None

        def capture_request(req, **kwargs):
            nonlocal captured_payload
            captured_payload = json.loads(req.data.decode())
            # Return mock response
            mock_body = MagicMock()
            mock_body.read.return_value = json.dumps({
                "choices": [{"message": {"content": '["Good AI coverage"]'}}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 10}
            }).encode()
            return MagicMock(__enter__=lambda s: mock_body, __exit__=lambda *a: None)

        with patch("src.clients.llm_openai.urllib.request.urlopen", side_effect=capture_request):
            suggest_feedback_tags(item)

        assert captured_payload is not None
        prompt_content = captured_payload["messages"][0]["content"]
        assert "OpenAI Releases GPT-5" in prompt_content, "Prompt should include article title"
        assert "TechCrunch" in prompt_content, "Prompt should include source name"

    def test_validates_tag_word_count(self, monkeypatch, sample_item):
        """Tags should be 1-4 words; longer tags should be filtered."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        # Mix of valid and invalid tags
        mock_response = json.dumps([
            "Good",  # 1 word - valid
            "Very relevant article",  # 3 words - valid
            "This is way too long to be a valid tag here",  # 10 words - invalid
            "Trusted source",  # 2 words - valid
        ])

        with patch("src.clients.llm_openai.urllib.request.urlopen") as mock_urlopen:
            mock_body = MagicMock()
            mock_body.read.return_value = json.dumps({
                "choices": [{"message": {"content": mock_response}}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 20}
            }).encode()
            mock_urlopen.return_value.__enter__.return_value = mock_body

            tags = suggest_feedback_tags(sample_item)

        # Should filter out the 10-word tag
        assert len(tags) == 3
        assert "Good" in tags
        assert "Very relevant article" in tags
        assert "Trusted source" in tags

    def test_returns_other_when_no_api_key(self, monkeypatch, sample_item):
        """Should return ['Other'] when OPENAI_API_KEY is not set."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        # Need to reload to pick up env var change
        import importlib
        import src.clients.llm_openai as llm_module
        importlib.reload(llm_module)

        tags = llm_module.suggest_feedback_tags(sample_item)

        assert tags == ["Other"]

    def test_returns_other_on_api_error(self, monkeypatch, sample_item):
        """Should return ['Other'] when API call fails."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        with patch("src.clients.llm_openai.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = Exception("API Error")

            tags = suggest_feedback_tags(sample_item)

        assert tags == ["Other"]

    def test_returns_other_on_invalid_json(self, monkeypatch, sample_item):
        """Should return ['Other'] when LLM returns invalid JSON."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        with patch("src.clients.llm_openai.urllib.request.urlopen") as mock_urlopen:
            mock_body = MagicMock()
            mock_body.read.return_value = json.dumps({
                "choices": [{"message": {"content": "not valid json"}}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 20}
            }).encode()
            mock_urlopen.return_value.__enter__.return_value = mock_body

            tags = suggest_feedback_tags(sample_item)

        assert tags == ["Other"]


class TestCachedTags:
    """Tests for tag caching in news_items."""

    def test_get_cached_tags_returns_none_when_not_set(self, db_conn, sample_item):
        """Should return None when no cached tags exist."""
        # Insert item first
        insert_news_items(db_conn, [sample_item])

        # Get item ID
        row = db_conn.execute("SELECT id FROM news_items LIMIT 1").fetchone()
        item_id = row[0]

        result = get_cached_tags(db_conn, item_id=item_id)
        assert result is None

    def test_set_and_get_cached_tags(self, db_conn, sample_item):
        """Should store and retrieve cached tags correctly."""
        # Insert item first
        insert_news_items(db_conn, [sample_item])

        # Get item ID
        row = db_conn.execute("SELECT id FROM news_items LIMIT 1").fetchone()
        item_id = row[0]

        tags = ["Relevant", "Good source", "Clear"]
        set_cached_tags(db_conn, item_id=item_id, tags=tags)

        result = get_cached_tags(db_conn, item_id=item_id)
        assert result == tags

    def test_cached_tags_persisted_as_json(self, db_conn, sample_item):
        """Tags should be stored as JSON in the database."""
        insert_news_items(db_conn, [sample_item])

        row = db_conn.execute("SELECT id FROM news_items LIMIT 1").fetchone()
        item_id = row[0]

        tags = ["Tag A", "Tag B"]
        set_cached_tags(db_conn, item_id=item_id, tags=tags)

        # Check raw value in DB
        raw = db_conn.execute("SELECT suggested_tags FROM news_items WHERE id = ?", (item_id,)).fetchone()[0]
        assert json.loads(raw) == tags


class TestReasonTagStorage:
    """Tests for reason_tag in item_feedback."""

    def test_upsert_stores_reason_tag(self, db_conn):
        """Should store reason_tag when provided."""
        start_run(db_conn, "run1", "2026-01-28T10:00:00+00:00", received=1)

        now = datetime.now(timezone.utc).isoformat()
        feedback_id = upsert_item_feedback(
            db_conn,
            run_id="run1",
            item_url="https://example.com/article",
            useful=1,
            reason_tag="Relevant topic",
            created_at=now,
            updated_at=now,
        )

        feedback = get_item_feedback(db_conn, run_id="run1", item_url="https://example.com/article")
        assert feedback is not None
        assert feedback["reason_tag"] == "Relevant topic"

    def test_upsert_without_reason_tag(self, db_conn):
        """Should work without reason_tag (defaults to None)."""
        start_run(db_conn, "run1", "2026-01-28T10:00:00+00:00", received=1)

        now = datetime.now(timezone.utc).isoformat()
        upsert_item_feedback(
            db_conn,
            run_id="run1",
            item_url="https://example.com/article",
            useful=1,
            created_at=now,
            updated_at=now,
        )

        feedback = get_item_feedback(db_conn, run_id="run1", item_url="https://example.com/article")
        assert feedback is not None
        assert feedback["reason_tag"] is None

    def test_upsert_updates_reason_tag(self, db_conn):
        """Should update reason_tag on subsequent upsert."""
        start_run(db_conn, "run1", "2026-01-28T10:00:00+00:00", received=1)

        now = datetime.now(timezone.utc).isoformat()

        # First submission with tag
        upsert_item_feedback(
            db_conn,
            run_id="run1",
            item_url="https://example.com/article",
            useful=1,
            reason_tag="First tag",
            created_at=now,
            updated_at=now,
        )

        # Second submission with different tag
        upsert_item_feedback(
            db_conn,
            run_id="run1",
            item_url="https://example.com/article",
            useful=0,
            reason_tag="Updated tag",
            created_at=now,
            updated_at=now,
        )

        feedback = get_item_feedback(db_conn, run_id="run1", item_url="https://example.com/article")
        assert feedback["reason_tag"] == "Updated tag"
        assert feedback["useful"] == 0


class TestFeedbackTagsUI:
    """Tests for feedback tags UI rendering."""

    def test_date_page_renders_feedback_input(self, tmp_path, monkeypatch):
        """Date page should render feedback text input and suggestion chips."""
        from fastapi.testclient import TestClient
        from src.main import app
        from src.db import get_conn, init_db
        from src.repo import insert_news_items, start_run, finish_run_ok
        from src.schemas import NewsItem
        from datetime import datetime, timezone

        db_file = tmp_path / "test.db"
        monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

        conn = get_conn()
        init_db(conn)

        # Insert a news item
        item = NewsItem(
            source="TestSource",
            url="https://example.com/article",
            published_at=datetime(2026, 1, 28, 12, 0, tzinfo=timezone.utc),
            title="Test Article Title",
            evidence="Some evidence",
        )
        insert_news_items(conn, [item])

        # Create a run so feedback is enabled
        start_run(conn, "run1", "2026-01-28T10:00:00+00:00", received=1)
        finish_run_ok(conn, "run1", "2026-01-28T10:05:00+00:00",
                      after_dedupe=1, inserted=1, duplicates=0)
        conn.close()

        client = TestClient(app)
        resp = client.get("/ui/date/2026-01-28")

        assert resp.status_code == 200
        html = resp.text

        # Check for feedback UI elements
        assert 'class="feedback-reason-input"' in html, "Should have feedback text input"
        assert 'class="feedback-reason-submit"' in html, "Should have submit button"
        assert 'class="feedback-tags"' in html or 'feedback-tag' in html, "Should have tag chips section"
        assert "Was this helpful?" in html, "Should have feedback prompt"


class TestTagSanitizer:
    """Tests for tag sanitization/filtering."""

    def test_blocks_profanity(self, monkeypatch, sample_item):
        """Should filter out tags containing profanity."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        # Reload module to pick up env var
        import importlib
        import src.clients.llm_openai as llm_module
        importlib.reload(llm_module)

        # Mock response with profanity
        mock_response = json.dumps(["Great article", "This is shit", "Good read"])

        with patch("src.clients.llm_openai.urllib.request.urlopen") as mock_urlopen:
            mock_body = MagicMock()
            mock_body.read.return_value = json.dumps({
                "choices": [{"message": {"content": mock_response}}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 20}
            }).encode()
            mock_urlopen.return_value.__enter__.return_value = mock_body

            tags = llm_module.suggest_feedback_tags(sample_item)

        assert "This is shit" not in tags
        assert "Great article" in tags
        assert "Good read" in tags

    def test_blocks_sensitive_content(self, monkeypatch, sample_item):
        """Should filter out tags with sensitive words."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        # Reload module to pick up env var
        import importlib
        import src.clients.llm_openai as llm_module
        importlib.reload(llm_module)

        mock_response = json.dumps(["Interesting take", "Full of hate", "Worth reading"])

        with patch("src.clients.llm_openai.urllib.request.urlopen") as mock_urlopen:
            mock_body = MagicMock()
            mock_body.read.return_value = json.dumps({
                "choices": [{"message": {"content": mock_response}}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 20}
            }).encode()
            mock_urlopen.return_value.__enter__.return_value = mock_body

            tags = llm_module.suggest_feedback_tags(sample_item)

        assert "Full of hate" not in tags
        assert "Interesting take" in tags


class TestFeedbackTagsAPI:
    """Tests for /feedback/item endpoint with reason_tag."""

    def test_submit_feedback_with_reason_tag(self, tmp_path, monkeypatch):
        """API should accept and store reason_tag."""
        from fastapi.testclient import TestClient
        from src.main import app
        from src.db import get_conn, init_db
        from src.repo import start_run

        db_file = tmp_path / "test.db"
        monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

        conn = get_conn()
        init_db(conn)
        start_run(conn, "run1", "2026-01-28T10:00:00+00:00", received=1)
        conn.close()

        client = TestClient(app)
        resp = client.post("/feedback/item", json={
            "run_id": "run1",
            "item_url": "https://example.com/article",
            "useful": True,
            "reason_tag": "Relevant topic"
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "saved"
        assert data["reason_tag"] == "Relevant topic"

    def test_submit_feedback_without_reason_tag(self, tmp_path, monkeypatch):
        """API should work without reason_tag."""
        from fastapi.testclient import TestClient
        from src.main import app
        from src.db import get_conn, init_db
        from src.repo import start_run

        db_file = tmp_path / "test.db"
        monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

        conn = get_conn()
        init_db(conn)
        start_run(conn, "run1", "2026-01-28T10:00:00+00:00", received=1)
        conn.close()

        client = TestClient(app)
        resp = client.post("/feedback/item", json={
            "run_id": "run1",
            "item_url": "https://example.com/article",
            "useful": False
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "saved"
        assert data["reason_tag"] is None


class TestFeedbackTagsEval:
    """Eval tests for tag suggestion quality. Run with RUN_LLM_EVALS=1."""

    @pytest.fixture(autouse=True)
    def reload_llm_module(self):
        """Reload LLM module to pick up API key from .env."""
        import importlib
        import src.clients.llm_openai as llm_module
        importlib.reload(llm_module)
        self.suggest_feedback_tags = llm_module.suggest_feedback_tags

    @llm_eval
    def test_tech_article_gets_tech_relevant_tags(self):
        """Tech article should get tech-relevant suggestions."""
        item = NewsItem(
            source="TechCrunch",
            url="https://techcrunch.com/2026/01/28/openai-gpt5",
            published_at=datetime.now(timezone.utc),
            title="OpenAI Releases GPT-5: A Major Leap in AI Reasoning",
            evidence="OpenAI announced GPT-5 today with significant improvements in reasoning capabilities.",
        )

        tags = self.suggest_feedback_tags(item)

        assert len(tags) >= 1, "Should return at least one tag"
        assert tags != ["Other"], "Should not fall back to Other for valid article"

        # At least one tag should be related to AI/tech
        tags_lower = " ".join(tags).lower()
        tech_keywords = ["ai", "tech", "openai", "gpt", "model", "reasoning", "coverage", "update"]
        has_tech_tag = any(kw in tags_lower for kw in tech_keywords)
        assert has_tech_tag, f"Expected tech-relevant tag, got: {tags}"

    @llm_eval
    def test_finance_article_gets_finance_relevant_tags(self):
        """Finance article should get finance-relevant suggestions."""
        item = NewsItem(
            source="Bloomberg",
            url="https://bloomberg.com/markets/fed-rates",
            published_at=datetime.now(timezone.utc),
            title="Fed Raises Interest Rates by 0.25% Amid Inflation Concerns",
            evidence="The Federal Reserve raised interest rates today citing persistent inflation.",
        )

        tags = self.suggest_feedback_tags(item)

        assert len(tags) >= 1
        assert tags != ["Other"]

        tags_lower = " ".join(tags).lower()
        finance_keywords = ["market", "fed", "rate", "finance", "economic", "timely", "trusted", "bloomberg"]
        has_finance_tag = any(kw in tags_lower for kw in finance_keywords)
        assert has_finance_tag, f"Expected finance-relevant tag, got: {tags}"

    @llm_eval
    def test_tags_are_short_and_actionable(self):
        """All returned tags should be 1-4 words."""
        item = NewsItem(
            source="Reuters",
            url="https://reuters.com/world/climate",
            published_at=datetime.now(timezone.utc),
            title="Global Climate Summit Reaches Historic Agreement",
            evidence="World leaders agreed to new emissions targets at the climate summit.",
        )

        tags = self.suggest_feedback_tags(item)

        for tag in tags:
            word_count = len(tag.split())
            assert 1 <= word_count <= 4, f"Tag '{tag}' has {word_count} words, expected 1-4"

    @llm_eval
    def test_different_articles_get_different_tags(self):
        """Different articles should get contextually different suggestions."""
        tech_item = NewsItem(
            source="Wired",
            url="https://wired.com/ai",
            published_at=datetime.now(timezone.utc),
            title="New AI Chip Promises 10x Performance Boost",
            evidence="A new AI chip architecture shows major performance gains.",
        )

        sports_item = NewsItem(
            source="ESPN",
            url="https://espn.com/nba",
            published_at=datetime.now(timezone.utc),
            title="Lakers Win Championship in Overtime Thriller",
            evidence="The Lakers secured the NBA championship in a dramatic overtime game.",
        )

        tech_tags = self.suggest_feedback_tags(tech_item)
        sports_tags = self.suggest_feedback_tags(sports_item)

        # Tags should be different (not identical sets)
        assert set(tech_tags) != set(sports_tags), \
            f"Different articles got identical tags: tech={tech_tags}, sports={sports_tags}"

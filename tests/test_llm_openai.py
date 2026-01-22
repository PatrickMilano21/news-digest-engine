import pytest
from unittest.mock import patch, Mock
import json

from src.clients.llm_openai import (
    summarize,
    _try_parse,
    _merge_usage,
    _elapsed_ms,
    _refuse,
)
from src.schemas import NewsItem
from src.llm_schemas.summary import SummaryResult
from src.error_codes import LLM_DISABLED, LLM_API_FAIL, LLM_PARSE_FAIL
from datetime import datetime, timezone



def test_summarize_no_api_key_returns_refusal():
    """Without API key, summarize() refuses immediately."""
    item = NewsItem(
        source="test",
        url="https://example.com",
        published_at=datetime.now(timezone.utc),
        title="Test Title",
        evidence="Test evidence"
    )

    # Patch the module-level constant to None
    with patch("src.clients.llm_openai.OPENAI_API_KEY", None):
        result, usage = summarize(item, "some evidence")

    assert isinstance(result, SummaryResult)
    assert result.refusal == LLM_DISABLED
    assert result.summary is None
    # Verify zero usage when no API call made
    assert usage["prompt_tokens"] == 0
    assert usage["completion_tokens"] == 0
    assert usage["cost_usd"] == 0.0
    assert usage["latency_ms"] == 0

def test_summarize_success_returns_summary_result():
    """When API returns valid JSON, return parsed SummaryResults."""
    item = NewsItem(
        source="test",
        url="https://example.com",
        published_at=datetime.now(timezone.utc),
        title="Test Title",
        evidence="Test evidence"
    )
        # Fake OpenAI response
    fake_llm_output = {
        "summary": "This is a test summary.",
        "tags": ["test"],
        "citations": [{"source_url": "https://example.com", "evidence_snippet": "Test evidence"}],
        "confidence": 0.9
    }

    fake_api_response = {
        "choices": [{"message": {"content": json.dumps(fake_llm_output)}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50}
    }

    # Mock urlopen to return our fake response
    mock_response = Mock()
    mock_response.read.return_value = json.dumps(fake_api_response).encode("utf-8")
    mock_response.__enter__ = Mock(return_value=mock_response)
    mock_response.__exit__ = Mock(return_value=False)

    with patch("src.clients.llm_openai.OPENAI_API_KEY", "fake-key"):
        with patch("urllib.request.urlopen", return_value=mock_response):
            result, usage = summarize(item, "Test evidence")

    assert isinstance(result, SummaryResult)
    assert result.summary == "This is a test summary."
    assert result.refusal is None
    assert len(result.citations) == 1
    # Verify usage dict returned
    assert usage["prompt_tokens"] == 100
    assert usage["completion_tokens"] == 50
    assert usage["cost_usd"] > 0
    assert usage["latency_ms"] >= 0


def test_summarize_api_error_returns_refusal():
    """When API call fails, return refusal."""
    item = NewsItem(
        source="test",
        url="https://example.com",
        published_at=datetime.now(timezone.utc),
        title="Test Title",
        evidence="Test evidence"
    )

    with patch("src.clients.llm_openai.OPENAI_API_KEY", "fake-key"):
        with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
            result, usage = summarize(item, "Test evidence")

    assert isinstance(result, SummaryResult)
    assert result.refusal == LLM_API_FAIL
    assert result.summary is None
    # API failed before returning, so zero usage
    assert usage["prompt_tokens"] == 0
    assert usage["cost_usd"] == 0.0


def test_summarize_retry_succeeds_after_parse_failure():
    """When first parse fails but retry succeeds, return valid result."""
    item = NewsItem(
        source="test",
        url="https://example.com",
        published_at=datetime.now(timezone.utc),
        title="Test Title",
        evidence="Test evidence"
    )

    # First response: malformed JSON
    malformed_response = {
        "choices": [{"message": {"content": '{"summary": "test",}'}}],  # trailing comma
        "usage": {"prompt_tokens": 100, "completion_tokens": 50}
    }

    # Second response (fix): valid JSON
    valid_output = {
        "summary": "Fixed summary.",
        "tags": [],
        "citations": [{"source_url": "https://example.com", "evidence_snippet": "evidence"}],
        "confidence": 0.8
    }
    fixed_response = {
        "choices": [{"message": {"content": json.dumps(valid_output)}}],
        "usage": {"prompt_tokens": 80, "completion_tokens": 40}
    }

    def make_mock_response(data):
        mock = Mock()
        mock.read.return_value = json.dumps(data).encode("utf-8")
        mock.__enter__ = Mock(return_value=mock)
        mock.__exit__ = Mock(return_value=False)
        return mock

    call_count = [0]
    def fake_urlopen(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return make_mock_response(malformed_response)
        else:
            return make_mock_response(fixed_response)

    with patch("src.clients.llm_openai.OPENAI_API_KEY", "fake-key"):
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result, usage = summarize(item, "Test evidence")

    assert isinstance(result, SummaryResult)
    assert result.summary == "Fixed summary."
    assert result.refusal is None
    # Usage should include both calls (100+80 prompt, 50+40 completion)
    assert usage["prompt_tokens"] == 180
    assert usage["completion_tokens"] == 90


def test_summarize_both_parses_fail_returns_refusal():
    """When both parse attempts fail, return parse failure refusal."""
    item = NewsItem(
        source="test",
        url="https://example.com",
        published_at=datetime.now(timezone.utc),
        title="Test Title",
        evidence="Test evidence"
    )

    # Both responses return garbage
    garbage_response = {
        "choices": [{"message": {"content": "not json at all"}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50}
    }

    mock_resp = Mock()
    mock_resp.read.return_value = json.dumps(garbage_response).encode("utf-8")
    mock_resp.__enter__ = Mock(return_value=mock_resp)
    mock_resp.__exit__ = Mock(return_value=False)

    with patch("src.clients.llm_openai.OPENAI_API_KEY", "fake-key"):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result, usage = summarize(item, "Test evidence")

    assert isinstance(result, SummaryResult)
    assert result.refusal == LLM_PARSE_FAIL
    assert result.summary is None
    # Usage tracked even when parse fails (we still made API calls)
    assert usage["prompt_tokens"] > 0
    assert usage["cost_usd"] > 0


def test_try_parse_valid_json_returns_summary_result():
    """Valid JSON matching schema returns SummaryResult."""
    raw = json.dumps({
        "summary": "Test summary",
        "tags": ["tech"],
        "citations": [{"source_url": "https://x.com", "evidence_snippet": "quote"}],
        "confidence": 0.95
    })

    result = _try_parse(raw)

    assert isinstance(result, SummaryResult)
    assert result.summary == "Test summary"


def test_try_parse_invalid_json_returns_none():
    """Invalid JSON returns None."""
    result = _try_parse("not json")
    assert result is None


def test_merge_usage_combines_token_counts():
    """Merge combines prompt and completion tokens."""
    u1 = {"prompt_tokens": 100, "completion_tokens": 50}
    u2 = {"prompt_tokens": 80, "completion_tokens": 40}

    result = _merge_usage(u1, u2)

    assert result["prompt_tokens"] == 180
    assert result["completion_tokens"] == 90


def test_elapsed_ms_returns_positive_int():
    """Elapsed time is a positive integer."""
    import time
    t0 = time.perf_counter()
    time.sleep(0.01)  # 10ms

    result = _elapsed_ms(t0)

    assert isinstance(result, int)
    assert result >= 10  # At least 10ms
    assert result < 1000  # Less than 1 second
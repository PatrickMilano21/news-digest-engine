# Import types module (used for type checking, though not explicitly used here)
import types
# Import time module to mock sleep function in tests
import time
# Import pytest for testing utilities like pytest.raises
import pytest

# Import the functions and exception class we're testing
from src.rss_fetch import (
    RSSFetchError,
    fetch_rss,
    fetch_rss_with_retry,
)
from src.error_codes import RATE_LIMITED, FETCH_TRANSIENT

# ---------- helpers ----------

# Fake response class that mimics urllib's HTTP response for testing
class FakeResponse:
    # Initialize with status code and response body (as bytes)
    def __init__(self, *, status: int, body: bytes):
        self.status = status
        self._body = body

    # Simulate reading the response body (returns the bytes we stored)
    def read(self) -> bytes:
        return self._body

    # Make this class work as a context manager (for "with" statements) - enter returns self
    def __enter__(self):
        return self

    # Exit method for context manager - return False means don't suppress exceptions
    def __exit__(self, exc_type, exc, tb):
        return False


# ---------- tests ----------

# Test that fetch_rss successfully returns the response body when HTTP status is 200
def test_fetch_rss_success(monkeypatch):
    # Fake function that replaces urllib.request.urlopen - returns a successful response
    def fake_urlopen(req, timeout):
        return FakeResponse(status=200, body=b"<rss>ok</rss>")

    # Replace urllib.request.urlopen with our fake function using monkeypatch
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    # Call fetch_rss and verify it returns the decoded response body
    out = fetch_rss("https://example.com/feed.xml")
    assert out == "<rss>ok</rss>"


# Test that fetch_rss raises RSSFetchError when HTTP status is not 200
def test_fetch_rss_non_200_raises(monkeypatch):
    # Fake function that returns a 500 error response
    def fake_urlopen(req, timeout):
        return FakeResponse(status=500, body=b"error")

    # Replace urllib.request.urlopen with our fake function
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    # Verify that fetch_rss raises RSSFetchError when status is not 200
    with pytest.raises(RSSFetchError):
        fetch_rss("https://example.com/feed.xml")


# Test that fetch_rss_with_retry successfully retries after a 429 error
def test_fetch_rss_with_retry_429_returns_rate_limited(monkeypatch):
    # Dictionary to track how many times our fake function was called
    calls = {"n": 0}

    # Fake function that fails on first call (429 error) but succeeds on second call
    def fake_fetch(url, *, timeout_s):
        calls["n"] += 1
    # Replace the actual fetch_rss function with our fake version
    monkeypatch.setattr("src.rss_fetch.fetch_rss", fake_fetch)

    result = fetch_rss_with_retry("https://example.com/feed.xml", attempts=3)
    # Call fetch_rss_with_retry and verify it succeeds after retry
    assert result.ok is False
    assert result.error_code == RATE_LIMITED
    assert calls["n"] == 1 #No retries for 429



# Test that fetch_rss_with_retry raises error after exhausting all retry attempts
def test_fetch_rss_with_retry_429_returns_rate_limited(monkeypatch):  
    """429 returns RATE_LIMITED immediately (no retry)."""
    calls = {"n": 0}

    def fake_fetch(url, *, timeout_s):
        calls["n"] += 1
        raise RSSFetchError("HTTP 429")

    monkeypatch.setattr("src.rss_fetch.fetch_rss", fake_fetch)        

    result = fetch_rss_with_retry("https://example.com/feed.xml",     
attempts=3)

    assert result.ok is False
    assert result.error_code == RATE_LIMITED
    assert calls["n"] == 1  # No retries for 429



# Test that fetch_rss_with_retry uses exponential backoff (sleep time doubles each retry)
def test_fetch_rss_with_retry_backoff(monkeypatch):
    # Track number of function calls
    calls = {"n": 0}
    # Track sleep durations to verify exponential backoff is working
    sleeps: list[float] = []

    # Fake function that fails twice, then succeeds on third attempt
    def fake_fetch(url, *, timeout_s):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RSSFetchError("HTTP 500")
        return "<rss>ok</rss>"

    # Fake sleep function that records how long we would have slept
    def fake_sleep(seconds):
        sleeps.append(seconds)

    # Replace both fetch_rss and time.sleep with our fake versions
    monkeypatch.setattr("src.rss_fetch.fetch_rss", fake_fetch)
    monkeypatch.setattr(time, "sleep", fake_sleep)

    # Call fetch_rss_with_retry with base_sleep of 0.5 seconds
    result = fetch_rss_with_retry(
        "https://example.com/feed.xml",
        attempts=3,
        base_sleep_s=0.5,
    )

    # Verify it eventually succeeds
    assert result.ok is True
    assert result.content == "<rss>ok</rss>"
    assert sleeps == [0.5, 1.0]

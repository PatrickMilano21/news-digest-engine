# Enable type hint syntax from future Python versions (allows using | for union types)
from __future__ import annotations

# Import time module for sleep/delay functionality
import time
# Import urllib modules for making HTTP requests
import urllib.request
import urllib.error


# Custom exception class for RSS fetching errors - used throughout the module for consistent error handling
class RSSFetchError(Exception):
    """Raised when RSS cannot be fetched (maps to RSS_FETCH_FAIL)."""


# Fetch RSS XML content from a URL - this is the base function without retries
def fetch_rss(url: str, *, timeout_s: float = 10.0) -> str:
    """Fetch RSS XML from a URL and return response text."""
    # Create an HTTP request object with the URL and custom User-Agent header
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "news-digest-engine/0.1"},
    )

    try:
        # Open the URL and get the response (using context manager for automatic cleanup)
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            # Get the HTTP status code from the response (some responses might not have status attribute)
            status = getattr(resp, "status", None)
            # Read the response body as bytes, then decode to UTF-8 string (replace errors with replacement characters)
            body = resp.read().decode("utf-8", errors="replace")

            # Check if status code is not 200 (OK) and raise error if so
            if status != 200:
                raise RSSFetchError(f"RSS_FETCH_FAIL: HTTP {status}")

            # Return the decoded response body as a string
            return body

    # Catch HTTP-specific errors (like 404, 500, etc.) and convert to our custom exception
    except urllib.error.HTTPError as exc:
        raise RSSFetchError(f"RSS_FETCH_FAIL: HTTP {exc.code}") from exc
    # Catch URL-related errors (like connection refused, DNS failure) and convert to our custom exception
    except urllib.error.URLError as exc:
        raise RSSFetchError(f"RSS_FETCH_FAIL: URL error: {exc.reason}") from exc
    # Catch timeout errors and convert to our custom exception
    except TimeoutError as exc:
        raise RSSFetchError("RSS_FETCH_FAIL: timeout") from exc


# Fetch RSS with automatic retry logic and exponential backoff for transient failures
def fetch_rss_with_retry(url: str,*,attempts: int = 3,base_sleep_s: float = 0.5,timeout_s: float = 10.0,) -> str:
    """Fetch RSS with retry/backoff for transient failures."""
    # Track the last exception in case we exhaust all retries
    last_exc: RSSFetchError | None = None

    # Loop through the specified number of attempts
    for i in range(attempts):
        try:
            # Try to fetch the RSS using the base function
            return fetch_rss(url, timeout_s=timeout_s)
        except RSSFetchError as exc:
            # If fetch fails, save the exception for later use
            last_exc = exc

            # Convert exception to string to check error type
            msg = str(exc)
            # Check if this is a 429 (Too Many Requests) error - these are usually transient
            is_429 = "HTTP 429" in msg
            # Check if this is a 5xx server error - these are usually transient server issues
            is_5xx = any(
                f"HTTP {code}" in msg
                for code in (
                    "500", "501", "502", "503", "504", "505",
                    "506", "507", "508", "509", "510", "511",
                )
            )

            # Decide if we should retry: only retry 429/5xx errors AND if we haven't used all attempts yet
            should_retry = (is_429 or is_5xx) and (i < attempts - 1)
            # If we shouldn't retry (e.g., 4xx client error or last attempt), raise the exception immediately
            if not should_retry:
                raise exc

            # Sleep before retrying using exponential backoff: base_sleep * 2^attempt_number
            # This means: 0.5s, 1.0s, 2.0s, 4.0s, etc. - each retry waits longer
            time.sleep(base_sleep_s * (2**i))

    # If we've exhausted all attempts and have an exception, raise it
    if last_exc is not None:
        raise last_exc
    # Fallback error if somehow we got here without an exception (shouldn't happen)
    raise RSSFetchError("RSS_FETCH_FAIL: unknown")

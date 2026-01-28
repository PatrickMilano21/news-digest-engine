# Enable type hint syntax from future Python versions (allows using | for union types)
from __future__ import annotations

from dataclasses import dataclass

from src.error_codes import FETCH_TIMEOUT, FETCH_TRANSIENT, RATE_LIMITED, FETCH_PERMANENT

# Import time module for sleep/delay functionality
import time
# Import urllib modules for making HTTP requests
import urllib.request
import urllib.error


# Custom exception class for RSS fetching errors - used throughout the module for consistent error handling
class RSSFetchError(Exception):
    """Raised when RSS cannot be fetched (used internally by fetch_rss)."""

@dataclass
class FetchResult:
    ok: bool
    content: str | None = None
    error_code: str | None = None
    error_message: str | None = None


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
    last_msg: str | None = None
    
    # Loop through the specified number of attempts
    for i in range(attempts):
        try:
            # Try to fetch the RSS using the base function
            content = fetch_rss(url, timeout_s=timeout_s)
            return FetchResult(ok=True, content=content)

        except RSSFetchError as exc:
            # If fetch fails, save the exception for later use
            last_msg = str(exc)
            #Classify the error
            is_timeout = "timeout" in last_msg.lower()
            is_429 = "HTTP 429" in last_msg
            is_5xx = any(f"HTTP {c}" in last_msg for c in range (500, 512))
            is_4xx = any(f"HTTP {c}" in last_msg for c in range (400, 500)) and not is_429

            #429: dont retry aggressively, return immediately
            if is_429:
                return FetchResult(ok=False, error_code=RATE_LIMITED, error_message=last_msg)
            # 4xx (non-429): permanent failure, no retry
            if is_4xx:
                return FetchResult(ok=False, error_code=FETCH_PERMANENT, error_message=last_msg)
            # timeout or 5xx: retry if attempts remain
            should_retry = (is_timeout or is_5xx) and (i< attempts - 1)
            if not should_retry:
                # Exhausted retries
                if is_timeout:
                    return FetchResult(ok=False, error_code=FETCH_TIMEOUT, error_message=last_msg)
                else:
                    return FetchResult(ok=False, error_code=FETCH_TRANSIENT, error_message=last_msg)       

            # Backoff before retry
            time.sleep(base_sleep_s * (2 ** i))

    # Fallback (shouldn't reach here)
    return FetchResult(ok=False, error_code=FETCH_TRANSIENT, error_message=last_msg or "unknown")
        

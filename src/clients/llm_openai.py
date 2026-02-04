from __future__ import annotations

import json
import os 
import time 
import urllib.request 
import urllib.error 

from src.schemas import NewsItem
from src.llm_schemas.summary import SummaryResult
from src.json_utils import safe_parse_json
from src.logging_utils import log_event
from src.error_codes import LLM_PARSE_FAIL, LLM_API_FAIL, LLM_DISABLED, COST_BUDGET_EXCEEDED
from src.db import db_conn
from src.repo import get_daily_spend


#Config
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-4o-mini"

#Cost estimates (per 1k tokens) - for logging only
COST_PER_1K_PROMPT = 0.00015
COST_PER_1K_COMPLETION = 0.0006

# Daily spend cap (default $1.00, configurable via env var)
LLM_DAILY_CAP_USD = float(os.environ.get("LLM_DAILY_CAP_USD", "5.00"))

SYSTEM_PROMPT = """You are a news summarization assistant. Given a news item and evidence, produce a JSON object.       

STRICT RULES (violations will be rejected):
1. Use ONLY the provided evidence. Do not use prior knowledge or external information.
2. If evidence is insufficient to write a factual summary, return: {"refusal": "insufficient evidence"}
3. Every factual claim in the summary MUST have a citation.
4. Citation evidence_snippet MUST be an EXACT quote from the provided evidence (copy-paste, not paraphrase).
5. Do not infer, extrapolate, or add information not explicitly stated in evidence.

Output JSON structure:
{
"summary": "1-2 sentence summary using only provided evidence",
"tags": ["tag1", "tag2"],
"citations": [
    {"source_url": "the item's URL", "evidence_snippet": "EXACT quote from evidence"}
],
"confidence": 0.0 to 1.0
}

If you cannot comply with all rules, return: {"refusal": "reason"}

Respond with ONLY the JSON object. No markdown, no explanation, no preamble.
"""

def summarize(item: NewsItem, evidence: str, *, day: str | None = None) -> tuple[SummaryResult, dict]:
    """
    Call OpenAI API and return a validated SummaryResult.
    Contract:
    -ALWAYS returns SummaryResult (never raises)
    -Either (summary + citations) OR (refusal)
    -Logs cost + latency on every call

    Args:
        item: NewsItem to summarize
        evidence: Source evidence text
        day: Optional YYYY-MM-DD date for budget checking. If provided and daily
             spend exceeds LLM_DAILY_CAP_USD, returns COST_BUDGET_EXCEEDED refusal.

    Returns:
        tuple of (SummaryResult, usage_dict)
        usage_dict contains: prompt_tokens, completion_tokens, cost_usd, latency_ms

    # NOTE: Returned as tuple to avoid polluting SummaryResult with operational concerns.
    # Can be refactored into a wrapper object later if needed.
    """

    if not OPENAI_API_KEY:
        log_event("llm_disabled", reason="OPENAI_API_KEY not set")
        return _refuse(LLM_DISABLED)

    # Check daily spend cap if day is provided
    if day is not None:
        with db_conn() as conn:
            daily_spend = get_daily_spend(conn, day=day)
        if daily_spend >= LLM_DAILY_CAP_USD:
            log_event("llm_budget_exceeded", day=day, spend=daily_spend, cap=LLM_DAILY_CAP_USD)
            return _refuse(COST_BUDGET_EXCEEDED)
    
    t0 = time.perf_counter()

    # Attempt 1: call API
    try:
        raw_response, usage = _call_openai(item, evidence)
    except Exception as exc:
        _log_call(latency_ms=_elapsed_ms(t0), status="api_fail", error=str(exc))
        return _refuse(LLM_API_FAIL)

    #Attempt 1: parse
    result = _try_parse(raw_response)
    if result:
        latency = _elapsed_ms(t0)
        cost = _compute_cost(usage["prompt_tokens"], usage["completion_tokens"])
        _log_call(latency_ms=latency, status="ok", **usage)
        return result, {
            "prompt_tokens": usage["prompt_tokens"],
            "completion_tokens": usage["completion_tokens"],
            "cost_usd": cost,
            "latency_ms": latency
        }
    
    # Attempt 2: retry with "fix JSON" prompt
    try:
        fixed_response, usage2 = _call_openai_fix(raw_response)
        usage = _merge_usage(usage, usage2)
    except Exception as e:
        _log_call(latency_ms=_elapsed_ms(t0), status="retry_api_fail", error=str(e), **usage)
        return _refuse(LLM_API_FAIL)

    result = _try_parse(fixed_response)
    if result:
        latency = _elapsed_ms(t0)
        cost = _compute_cost(usage["prompt_tokens"], usage["completion_tokens"])
        _log_call(latency_ms=latency, status="ok_after_retry", **usage)
        return result, {
            "prompt_tokens": usage["prompt_tokens"],
            "completion_tokens": usage["completion_tokens"],
            "cost_usd": cost,
            "latency_ms": latency
        }

    # Both attempts failed
    latency = _elapsed_ms(t0)
    cost = _compute_cost(usage["prompt_tokens"], usage["completion_tokens"])
    _log_call(latency_ms=_elapsed_ms(t0), status="parse_fail", **usage)
    refusal_result, _ = _refuse(LLM_PARSE_FAIL)
    return refusal_result, {
        "prompt_tokens": usage["prompt_tokens"],
        "completion_tokens": usage["completion_tokens"],
        "cost_usd": cost,
        "latency_ms": latency
    }       
    


def _refuse(reason: str) -> tuple[SummaryResult, dict]:
    """Return a valid SummaryResult with refusal, plus zero usage."""
    return SummaryResult(refusal=reason), {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cost_usd": 0.0,
        "latency_ms": 0
    }

def _try_parse(raw):
    """Attempt to parse raw LLM output into SummaryResults. Returns None on failure"""
    data = safe_parse_json(raw)
    if data is None:
        return None

    try:
        return SummaryResult(**data)
    except Exception:
        return None


def _call_openai(item: NewsItem, evidence: str) -> tuple[str, dict]:
    """Make OpenAI API call. Returns (response_text, usage_dict). Raises on error."""
    user_content = f"""News item:
Title: {item.title}
Source: {item.source}
URL: {item.url}
Published: {item.published_at.isoformat()}

Evidence:
{evidence}
"""
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.0,
        "max_tokens": 500
    }

    req = urllib.request.Request(
        OPENAI_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers ={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
    )

    with urllib.request.urlopen(req, timeout=30.0) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    content = body["choices"][0]["message"]["content"]
    usage = body.get("usage", {})

    return content, {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0)
    }


def _call_openai_fix(malformed_json: str) -> tuple[str, dict]:
    """Ask OpenAI to fix malformed JSON. Returns (response_text, usage_dict)."""
    fix_prompt = f"""The following JSON is malformed. Fix it to match this exact schema:
{{
"summary": "string",
"tags": ["string"],
"citations": [{{"source_url": "string", "evidence_snippet": "string"}}],
"confidence": number
}}

Malformed JSON: {malformed_json}

Return ONLY the corrected JSON, nothing else.
"""
    
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": fix_prompt}],
        "temperature": 0.0,
        "max_tokens": 500
    }
    
    req = urllib.request.Request(
        OPENAI_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
    )

    with urllib.request.urlopen(req, timeout=30.0) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    content = body["choices"][0]["message"]["content"]
    usage = body.get("usage", {})
    
    return content, {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0)
    }


def _merge_usage(u1: dict, u2: dict) -> dict:
    """Combine token counts from two API calls."""
    return {
        "prompt_tokens": u1.get("prompt_tokens", 0) + u2.get("prompt_tokens", 0),
        "completion_tokens": u1.get("completion_tokens", 0) + u2.get("completion_tokens", 0)
    }


def _log_call(*, latency_ms: int, status: str, 
            prompt_tokens: int = 0, completion_tokens: int = 0, **extra):
    """Log every LLM call with cost + latency."""
    total_tokens = prompt_tokens + completion_tokens
    cost_usd = (prompt_tokens / 1000 * COST_PER_1K_PROMPT + 
                completion_tokens / 1000 * COST_PER_1K_COMPLETION)
    
    # TODO: attach run_id when summarize() is called from pipeline context
    log_event("llm_call",
        model=MODEL,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        latency_ms=latency_ms,
        cost_usd=round(cost_usd, 6),
        cache_hit=False,
        status=status,
        **extra
    )


def _elapsed_ms(t0: float) -> int:
    """Calculate elapsed milliseconds since t0."""
    return int((time.perf_counter() - t0) * 1000)

def _compute_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """Compute cost in USD from token counts."""
    return round(
        prompt_tokens / 1000 * COST_PER_1K_PROMPT +
        completion_tokens / 1000 * COST_PER_1K_COMPLETION,
        6
    )


# --- Feedback Tag Suggestion (Milestone 3a) ---

# Basic blocklist for profanity/sensitive content
_TAG_BLOCKLIST = {
    # Profanity
    "fuck", "shit", "damn", "ass", "bitch", "crap",
    # Sensitive
    "hate", "kill", "die", "racist", "sexist",
}


def _sanitize_tag(tag: str) -> str | None:
    """Filter out profanity/sensitive tags. Returns None if blocked."""
    tag_lower = tag.lower()
    for blocked in _TAG_BLOCKLIST:
        if blocked in tag_lower:
            log_event("tag_blocked", tag=tag, reason="blocklist")
            return None
    return tag

TAG_SUGGESTION_PROMPT = """Suggest 3-5 casual, conversational feedback reasons (1-4 words) for this article. Write like you're texting a friend about why you liked or didn't like it.

Article:
Title: {title}
Source: {source}

Be specific to THIS article. Use natural, relatable language. Mix positive and constructive.

Examples of the vibe we want:
- Tech: ["Finally explained well", "Too much hype", "Needed more examples", "Actually useful"]
- Finance: ["Made me smarter", "Too jargon-heavy", "Great timing", "Where's the data?"]
- Sports: ["What a game!", "Biased take", "Love the stats", "Clickbait title"]
- Science: ["Mind = blown", "Too dumbed down", "Solid research", "Just an ad"]

Return ONLY a JSON array. No markdown.
"""


def suggest_feedback_tags(item: NewsItem) -> list[str]:
    """
    Suggest 3-5 feedback tags for an item using LLM.

    Contract:
    - ALWAYS returns a list (never raises)
    - Returns ["Other"] on any failure (API error, parse error, no API key)
    - Exempt from daily cost cap (cheap call, separate concern)
    - Tags are 1-2 words each, generic/reusable

    Args:
        item: NewsItem to generate tags for

    Returns:
        List of 3-5 tag strings, or ["Other"] on failure
    """
    if not OPENAI_API_KEY:
        log_event("tag_suggestion_disabled", reason="OPENAI_API_KEY not set")
        return ["Other"]

    t0 = time.perf_counter()

    try:
        prompt = TAG_SUGGESTION_PROMPT.format(title=item.title, source=item.source)

        payload = {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,  # Slight variation for diverse tags
            "max_tokens": 100
        }

        req = urllib.request.Request(
            OPENAI_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            }
        )

        with urllib.request.urlopen(req, timeout=15.0) as resp:
            body = json.loads(resp.read().decode("utf-8"))

        content = body["choices"][0]["message"]["content"]
        usage = body.get("usage", {})

        # Parse JSON array
        tags = safe_parse_json(content)

        if not isinstance(tags, list) or len(tags) < 1:
            log_event("tag_suggestion_parse_fail", raw=content)
            return ["Other"]

        # Validate: all items are strings, 1-4 words, limit to 5
        # Also filter out profanity/sensitive content
        valid_tags = []
        for tag in tags[:5]:
            if isinstance(tag, str) and 1 <= len(tag.split()) <= 4:
                cleaned = _sanitize_tag(tag.strip())
                if cleaned:
                    valid_tags.append(cleaned)

        if len(valid_tags) < 1:
            log_event("tag_suggestion_validation_fail", tags=tags)
            return ["Other"]

        latency = _elapsed_ms(t0)
        cost = _compute_cost(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))

        log_event("tag_suggestion_ok",
            model=MODEL,
            tags=valid_tags,
            latency_ms=latency,
            cost_usd=cost
        )

        return valid_tags

    except Exception as exc:
        log_event("tag_suggestion_error", error=str(exc), latency_ms=_elapsed_ms(t0))
        return ["Other"]

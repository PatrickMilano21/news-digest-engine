from __future__ import annotations

import json
import os 
import time 
import urllib.request 
import urllib.error 

from src.schemas import NewsItem
from src.llm_schemas.summary import SummaryResult, Citation
from src.json_utils import safe_parse_json
from src.logging_utils import log_event
from src.error_codes import LLM_PARSE_FAIL, LLM_API_FAIL, LLM_DISABLED


#Config
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-4o-mini"

#Cost estimates (per 1k tokens) - for logging only
COST_PER_1K_PROMPT = 0.00015
COST_PER_1K_COMPLETION = 0.0006

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

def summarize(item: NewsItem, evidence: str) -> SummaryResult:
    """
    Call OpenAI API and return a validated SummaryResult.
    Contract: 
    -ALWAYS returns SummaryResult (never raises)
    -Either (summary + citations) OR (refusal)
    -Logs cost + latency on every call
    """
    if not OPENAI_API_KEY:
        return _refuse(LLM_DISABLED)
    
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
        _log_call(latency_ms=_elapsed_ms(t0), status="ok", **usage)
        return result
    
    # Attempt 2: retry with "fix JSON" prompt
    try:
        fixed_response, usage2 = _call_openai_fix(raw_response)
        usage = _merge_usage(usage, usage2)
    except Exception as e:
        _log_call(latency_ms=_elapsed_ms(t0), status="retry_api_fail", error=str(e), **usage)
        return _refuse(LLM_API_FAIL)

    result = _try_parse(fixed_response)
    if result:
        _log_call(latency_ms=_elapsed_ms(t0), status="ok_after_retry", **usage)
        return result

    # Both attempts failed
    _log_call(latency_ms=_elapsed_ms(t0), status="parse_fail", **usage)
    return _refuse(LLM_PARSE_FAIL)


def _refuse(reason: str) -> SummaryResult:
    """Return a valid SummaryResult with refusal."""
    return SummaryResult(refusal=reason)

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


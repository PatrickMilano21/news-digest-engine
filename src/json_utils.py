import json
import re

def safe_parse_json(raw: str) -> dict | None:
    """
    Parse messy LLM JSON safely.

    - Never crash
    - Never return partial garbage
    - Handle common LLM quirks (markdown fences)

    NOTE:
    - Does NOT attempt partial recovery (e.g., trailing commas, missing braces)
    - Returns None instead of guessing

    This aligns with refusal > corruption philosophy.
    """

    if not raw or not raw.strip():
        return None
    
    text = raw.strip()
    # Strip markdown code fences: ```json ... ``` or ``` ... ```
    fence_pattern = r'^```(?:json)?\s*\n?(.*?)\n?```$'
    match = re.match(fence_pattern, text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


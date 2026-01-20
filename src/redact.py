

import re
from typing import Any 


EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
PHONE_PATTERN = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'



def redact(text: str) -> str:
    """REPLACE emails and phone numbers with redaction markets."""
    result = re.sub(EMAIL_PATTERN, '[REDACTED_EMAIL]', text)
    result = re.sub(PHONE_PATTERN, '[REDACTED_PHONE]', result)
    return result

def sanitize(obj: Any) -> Any:
    """Recursively redact strings in dicts, lists, or plain values."""
    if isinstance(obj, str):
        return redact(obj)
    if isinstance(obj, dict):
        return {k:  sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(item) for item in obj]
    return obj
    
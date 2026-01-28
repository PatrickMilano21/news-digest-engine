from src.redact import redact, sanitize


def test_redact_email():
    assert redact("contact foo@bar.com") == "contact [REDACTED_EMAIL]"


def test_redact_phone_dashes():
    assert redact("call 555-123-4567") == "call [REDACTED_PHONE]"


def test_redact_phone_dots():
    assert redact("call 555.123.4567") == "call [REDACTED_PHONE]"


def test_redact_mixed():
    text = "email foo@bar.com or call 555-123-4567"
    expected = "email [REDACTED_EMAIL] or call [REDACTED_PHONE]"
    assert redact(text) == expected


def test_redact_clean_text():
    assert redact("no pii here") == "no pii here"


def test_sanitize_nested_dict():
    obj = {
        "user": "foo@bar.com",
        "nested": {"phone": "555-123-4567"}
    }
    result = sanitize(obj)
    assert result["user"] == "[REDACTED_EMAIL]"
    assert result["nested"]["phone"] == "[REDACTED_PHONE]"


def test_sanitize_list():
    obj = ["foo@bar.com", 123, None]
    result = sanitize(obj)
    assert result == ["[REDACTED_EMAIL]", 123, None]
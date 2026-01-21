import pytest
import json
from src.json_utils  import safe_parse_json


def test_valid_json():
    assert safe_parse_json('{"a": 1}') == {"a": 1}


def test_json_with_json_fence():
    raw = '```json\n{"a": 1}\n```'
    assert safe_parse_json(raw) == {"a": 1}


def test_json_with_plain_fence():
    raw = '```\n{"a": 1}\n```'
    assert safe_parse_json(raw) == {"a": 1}


def test_json_with_nested_structure():
    raw = '{"summary": "test", "tags": ["a", "b"]}'
    result = safe_parse_json(raw)
    assert result == {"summary": "test", "tags": ["a", "b"]}


def test_invalid_json_returns_none():
    assert safe_parse_json('not json at all') is None


def test_empty_string_returns_none():
    assert safe_parse_json('') is None


def test_whitespace_only_returns_none():
    assert safe_parse_json('   \n  ') is None


def test_json_with_trailing_text_returns_none():
    # We don't try to recover partial JSON
    assert safe_parse_json('{"a": 1} and some extra text') is None


def test_trailing_comma_returns_none():
    # Invalid JSON - we don't fix it
    assert safe_parse_json('{"a": 1,}') is None
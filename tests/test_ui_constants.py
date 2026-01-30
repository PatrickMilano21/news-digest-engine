"""Tests for shared UI constants."""
from src.ui_constants import Colors, Strings, format_date_short, format_datetime_friendly


def test_colors_are_hex():
    """Color values should be valid hex codes."""
    assert Colors.LINK.startswith("#")
    assert Colors.SUMMARY_BG.startswith("#")
    assert Colors.REFUSAL_BORDER.startswith("#")


def test_strings_refusal_message():
    """Refusal message should be consistent."""
    assert "not enough source content" in Strings.REFUSAL_MESSAGE


def test_stories_count_singular():
    """Stories count handles singular correctly."""
    assert Strings.stories_count(1) == "1 story from today's feeds"


def test_stories_count_plural():
    """Stories count handles plural correctly."""
    result = Strings.stories_count(5)
    assert "5 stories" in result


def test_sources_label_singular():
    """Sources label handles singular correctly."""
    assert Strings.sources_label(1) == "Sources: 1 article"


def test_sources_label_plural():
    """Sources label handles plural correctly."""
    assert "3 articles" in Strings.sources_label(3)


def test_format_date_short():
    """Date formatting returns readable format."""
    result = format_date_short("2026-01-14T12:00:00+00:00")
    assert result == "Jan 14, 2026"


def test_format_date_short_handles_invalid():
    """Date formatting handles invalid input gracefully."""
    assert format_date_short("invalid") == "invalid"[:10]
    assert format_date_short("") == ""


def test_format_datetime_friendly():
    """Datetime formatting returns readable format."""
    result = format_datetime_friendly("2026-01-14T15:30:00+00:00")
    assert "Jan 14, 2026" in result
    assert "PM" in result


def test_format_datetime_friendly_handles_invalid():
    """Datetime formatting handles invalid input gracefully."""
    assert format_datetime_friendly("invalid") == ""

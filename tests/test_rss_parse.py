import pytest

from src.rss_parse import RSSParseError, parse_rss

GOOD_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example Feed</title>
    <item>
      <title>First</title>
      <link>https://example.com/1</link>
      <pubDate>Fri, 10 Jan 2026 12:00:00 GMT</pubDate>
      <description>Evidence one</description>
    </item>
    <item>
      <title>Second</title>
      <link>https://example.com/2</link>
      <pubDate>Fri, 10 Jan 2026 13:00:00 GMT</pubDate>
      <description>Evidence two</description>
    </item>
  </channel>
</rss>
"""

def test_parse_rss_valid_xml_returns_items():
    out = parse_rss(GOOD_RSS, source="example")
    assert len(out) == 2
    assert out[0].title == "First"
    assert str(out[0].url) == "https://example.com/1"
        #becaue url is a Pydantic HttpUrl type
    assert out[0].evidence == "Evidence one"


MISSING_LINK_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example Feed</title>
    <item>
      <title>Bad Item</title>
      <pubDate>Fri, 10 Jan 2026 12:00:00 GMT</pubDate>
      <description>No link here</description>
    </item>
    <item>
      <title>Good Item</title>
      <link>https://example.com/good</link>
      <pubDate>Fri, 10 Jan 2026 12:00:00 GMT</pubDate>
      <description>Ok</description>
    </item>
  </channel>
</rss>
"""

def test_parse_rss_skip_items_missing_required_fields():
    out = parse_rss(MISSING_LINK_RSS, source="example")
    assert len(out) == 1
    assert out[0].title == "Good Item"
    assert str(out[0].url) == "https://example.com/good"

def test_parse_rss_perserves_item_order():
    out = parse_rss(GOOD_RSS, source="example")
    assert [x.title for x in out] == ["First", "Second"]

def test_parse_rss_invalid_xml_raises():
    bad = "<rss><channel><item></rss>"  # malformed / mismatched tags
    with pytest.raises(RSSParseError):
        parse_rss(bad, source="example")


# src/rss_parse.py
from __future__ import annotations

from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET

from src.schemas import NewsItem


class RSSParseError(ValueError):
    """Raised when RSS XML cannot be parsed (maps to RSS_PARSE_FAIL)."""


def parse_rss(xml: str, *, source: str, use_item_source: bool = False) -> list[NewsItem]:
    """
    Convert an RSS XML document (string) into NewsItem objects.

    Rules:
    - Parse <item> elements
    - title + link required
    - pubDate required + must parse, else skip the item
    - evidence from <description> if present else ""
    - Preserve order
    - Malformed XML -> raise RSSParseError

    Args:
        xml: RSS XML string
        source: Default source for all items
        use_item_source: If True, use <source> element from each item if present
    """
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise RSSParseError(f"RSS_PARSE_FAIL: malformed XML: {exc}") from exc

    items = root.findall("./channel/item")
    out: list[NewsItem] = []

    def text_of(elem: ET.Element, path: str) -> str | None:
        found = elem.find(path)
        if found is None or found.text is None:
            return None
        text = found.text.strip()
        return text if text else None

    for it in items:
        title = text_of(it, "title")
        link = text_of(it, "link")
        pub = text_of(it, "pubDate")
        evidence = text_of(it, "description") or ""

        if title is None or link is None or pub is None:
            continue

        try:
            published_at = parsedate_to_datetime(pub)
        except Exception:
            continue

        # Use per-item source if enabled and present
        item_source = source
        if use_item_source:
            xml_source = text_of(it, "source")
            if xml_source:
                item_source = xml_source

        out.append(
            NewsItem(
                source=item_source,
                url=link,
                published_at=published_at,
                title=title,
                evidence=evidence,
            )
        )

    return out

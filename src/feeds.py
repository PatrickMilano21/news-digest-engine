# src/feeds.py
"""Feed URLs for ingestion. Hardcoded for now, easy to swap later."""

FEEDS = [
    {"url": "https://feeds.arstechnica.com/arstechnica/technology-lab", "source": "arstechnica"},
    {"url": "https://www.theverge.com/rss/index.xml", "source": "theverge"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml", "source": "nytimes"},
]

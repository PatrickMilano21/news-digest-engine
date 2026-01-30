# tests/test_run_rss_ingest.py
from __future__ import annotations

import pytest

from src.repo import get_latest_run
from src.db import get_conn, init_db
from src.run import run_rss_ingest
from src.rss_fetch import RSSFetchError


GOOD_RSS_1 = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Feed</title>
    <item>
      <title>A</title>
      <link>https://example.com/a</link>
      <pubDate>Fri, 10 Jan 2026 12:00:00 GMT</pubDate>
      <description>e1</description>
    </item>
  </channel>
</rss>
"""

GOOD_RSS_2_DUP = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Feed</title>
    <item>
      <title>A</title>
      <link>https://example.com/a</link>
      <pubDate>Fri, 10 Jan 2026 12:00:00 GMT</pubDate>
      <description>e1</description>
    </item>
    <item>
      <title>B</title>
      <link>https://example.com/b</link>
      <pubDate>Fri, 10 Jan 2026 13:00:00 GMT</pubDate>
      <description>e2</description>
    </item>
  </channel>
</rss>
"""

BAD_XML = "<rss><channel><item></rss>"


def _latest():
    conn = get_conn()
    try:
        init_db(conn)
        return get_latest_run(conn)
    finally:
        conn.close()


def test_run_rss_fixtures_ingests_and_records_ok(tmp_path):
    (tmp_path / "f1.xml").write_text(GOOD_RSS_1, encoding="utf-8")
    (tmp_path / "f2.xml").write_text(GOOD_RSS_1, encoding="utf-8")

    out = run_rss_ingest(
        feed_specs=[("s1", "f1.xml"), ("s2", "f2.xml")],
        mode="fixtures",
        fixtures_dir=str(tmp_path),
    )

    assert out["run_id"]
    assert out["inserted"] > 0

    latest = _latest()
    assert latest["run_id"] == out["run_id"]
    assert latest["status"] == "ok"
    assert latest["inserted"] == out["inserted"]


def test_run_rss_dedupes_across_feeds(tmp_path):
    (tmp_path / "f1.xml").write_text(GOOD_RSS_1, encoding="utf-8")
    (tmp_path / "f2.xml").write_text(GOOD_RSS_2_DUP, encoding="utf-8")

    out = run_rss_ingest(
        feed_specs=[("s1", "f1.xml"), ("s2", "f2.xml")],
        mode="fixtures",
        fixtures_dir=str(tmp_path),
    )

    assert out["received"] >= out["after_dedupe"]
    assert out["duplicates"] >= 1


def test_run_rss_fetch_failure_records_rss_fetch_fail(monkeypatch, tmp_path):
    def fake_fetch(url, *, attempts=3, base_sleep_s=0.5, timeout_s=10.0):
        raise RSSFetchError("RSS_FETCH_FAIL: HTTP 500")

    monkeypatch.setattr("src.run.fetch_rss_with_retry", fake_fetch)

    with pytest.raises(RSSFetchError):
        run_rss_ingest(
            feed_specs=[("s1", "https://example.com/feed")],
            mode="prod",
            fixtures_dir=str(tmp_path),
        )

    latest = _latest()
    assert latest["status"] == "error"
    assert latest["error_type"] == "RSS_FETCH_FAIL"


def test_run_rss_parse_failure_records_rss_parse_fail(tmp_path):
    (tmp_path / "bad.xml").write_text(BAD_XML, encoding="utf-8")

    with pytest.raises(Exception):
        run_rss_ingest(
            feed_specs=[("s1", "bad.xml")],
            mode="fixtures",
            fixtures_dir=str(tmp_path),
        )

    latest = _latest()
    assert latest["status"] == "error"
    assert latest["error_type"] == "RSS_PARSE_FAIL"
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from evals.cases import EvalCase, load_cases
from evals.runner import run_eval_case
from evals.taxonomy import (
    EVAL_FIXTURE_READ_FAIL,
    EVAL_RSS_PARSE_FAIL,
    EVAL_MISMATCH_KEYWORD,
)
from src.scoring import RankConfig

NOW = datetime(2026, 1, 14, 23, 59, 59, tzinfo=timezone.utc)

def test_error_code_fixture_read_fail():
    case = EvalCase(
        case_id="bad_fixture_path",
        fixture_path="fixtures/evals/does_not_exist.xml",
        source="fixture",
        expected_titles=[],
        top_n=2,
        cfg=RankConfig(search_fields=["title"]),
    )

    out = run_eval_case(case, now=NOW)

    assert out["pass"] is False
    assert out["error_code"] == EVAL_FIXTURE_READ_FAIL

def test_error_code_rss_parse_fail(tmp_path: Path):
    bad_xml = tmp_path / "bad.xml"
    bad_xml.write_text("<rss><channel>", encoding="utf-8")  # malformed XM

    case = EvalCase(
        case_id="bad_rss_parse",
        fixture_path=str(bad_xml),
        source="fixture",
        expected_titles=[],
        top_n=2,
        cfg=RankConfig(search_fields=["title"]),
    )

    out = run_eval_case(case, now=NOW)
    assert out["pass"] is False
    assert out["error_code"] == EVAL_RSS_PARSE_FAIL


def test_error_code_none_on_pass():
    cases = load_cases()
    assert len(cases) > 0
    case = cases[0]
    out = run_eval_case(case, now=NOW)

    assert out["pass"] is True
    assert out["error_code"] is None

def test_error_code_keyword_mismatch(tmp_path: Path):
    fx = tmp_path / "kw.xml"
    fx.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Fixture Feed</title>
    <item>
      <title>No keyword</title>
      <link>https://example.com/nk</link>
      <pubDate>Wed, 14 Jan 2026 10:00:00 GMT</pubDate>
      <description></description>
    </item>
    <item>
      <title>Has merger keyword</title>
      <link>https://example.com/m</link>
      <pubDate>Wed, 14 Jan 2026 10:00:00 GMT</pubDate>
      <description></description>
    </item>
  </channel>
</rss>
""",
        encoding="utf-8",
    )

    case = EvalCase(
        case_id="kw_mismatch_case",
        fixture_path=str(fx),
        source="fixture",
        # intentionally wrong expected order to force mismatch
        expected_titles=["No keyword", "Has merger keyword"],
        top_n=2,
        cfg=RankConfig(keyword_boosts={"merger": 5.0}, search_fields=["title"]),
    )

    out = run_eval_case(case, now=NOW)
    assert out["pass"] is False
    assert out["error_code"] == EVAL_MISMATCH_KEYWORD


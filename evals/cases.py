from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.scoring import RankConfig


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    fixture_path: str
    source: str
    expected_titles: list[str]
    top_n: int 
    cfg: RankConfig

def load_cases() -> list[EvalCase]:
    fx_keyword = str(Path("fixtures") / "evals" / "case_keyword_boost.xml")
    fx_recency = str(Path("fixtures") / "evals" / "case_recency.xml")
    fx_title_vs_evidence = str(Path("fixtures") / "evals" / "case_title_vs_evidence.xml")
    fx_tie_break = str(Path("fixtures") / "evals" / "case_tie_break.xml")

    cases: list[EvalCase] = []
    
    def add(case_id: str, fixture_path: str, expected_titles: list[str], *, top_n: int, cfg: RankConfig) -> None:
        cases.append(
            EvalCase(
                case_id=case_id,
                fixture_path=fixture_path,
                source="fixture",
                expected_titles=expected_titles,
                top_n=top_n,
                cfg=cfg,
            )
        )
    # Group 1: keyword boost (relevance via title)
    for boost in (1.0, 2.0, 3.0, 5.0, 8.0):
        add(
            f"kw_merger_title_boost_{int(boost)}",
            fx_keyword,
            ["Company A announces merger talks", "Company B quarterly results"],
            top_n=2,
            cfg=RankConfig(keyword_boosts={"merger": boost}, search_fields=["title"]),
        )

    # Group 2: recency ordering
    for half_life in (3.0, 6.0, 12.0, 24.0, 72.0, 168.0):
        add(
            f"recency_half_life_{int(half_life)}",
            fx_recency, 
            ["Newer item", "Older item"],
            top_n=2,
            cfg=RankConfig(recency_half_life_hours=half_life, search_fields=["title"]),
        )

    # Group 3: title vs evidence behavior
    for boost in (1.0, 2.0, 3.0, 5.0, 8.0):
        # title-only should pick the title match
        add(
            f"title_only_merger_boost_{int(boost)}",
            fx_title_vs_evidence,
            ["Company Y announces merger talks", "Company X quarterly results", "Company Z product launch"],
            top_n=3,
            cfg=RankConfig(keyword_boosts={"merger": boost}, search_fields=["title"]),
        )
        # evidence-only should pick the evidence match
        add(
            f"evidence_only_merger_boost_{int(boost)}",
            fx_title_vs_evidence,
            ["Company X quarterly results", "Company Y announces merger talks", "Company Z product launch"],
            top_n=3,
            cfg=RankConfig(keyword_boosts={"merger": boost}, search_fields=["evidence"]),
        )
        # both fields: both match "merger", but title match item has it in title; this ordering is deterministic with this fixture
        add(
            f"both_fields_merger_boost_{int(boost)}",
            fx_title_vs_evidence,
            ["Company X quarterly results", "Company Y announces merger talks", "Company Z product launch"],
            top_n=3,
            cfg=RankConfig(keyword_boosts={"merger": boost}, search_fields=["title", "evidence"]),
        )

    # Group 4: tie-break determinism (same score, same timestamp)
    for _i in range(1, 25):
        add(
            f"tie_break_order_{_i}",
            fx_tie_break,
            ["Item A", "Item B"],
            top_n=2,
            cfg=RankConfig(search_fields=["title"]),
        )

    # Group 5: Deliberately failing case (for debugging drill)
    # Uncomment to simulate eval failure:
    # add(
    #     "keyword_mismatch_deliberate_fail",
    #     fx_keyword,
    #     ["Company B quarterly results", "Company A announces merger talks"],  # WRONG order
    #     top_n=2,
    #     cfg=RankConfig(keyword_boosts={"merger": 5.0}, search_fields=["title"]),
    # )

    # Sanity: exactly 50
    assert len(cases) == 50, f"expected 50 cases, got {len(cases)}"
    return cases

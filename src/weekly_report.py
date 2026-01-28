from datetime import datetime, timedelta
from pathlib import Path

from src.repo import report_top_sources, report_failures_by_code
from src.scoring import RankConfig


WEEKLY_REPORT_PATH = Path("artifacts/weekly_report.md")


def write_weekly_report(*, conn, end_day: str, days: int = 7) -> str:
    """
    Generate a weekly summary report as markdown.
    Returns the path to the written file.
    """
    # Calculate date range
    end_date = datetime.strptime(end_day, "%Y-%m-%d").date()
    start_date = end_date - timedelta(days=days - 1)
    start_day = start_date.isoformat()

    # Fetch data
    top_sources = report_top_sources(conn, end_day=end_day, days=days) if conn else []
    failures = report_failures_by_code(conn, end_day=end_day, days=days) if conn else {}
    config = RankConfig()

    # Format top sources section
    if top_sources:
        sources_lines = ["| Source | Count |", "|--------|-------|"]
        for s in top_sources:
            sources_lines.append(f"| {s['source']} | {s['count']} |")
        sources_section = "\n".join(sources_lines)
    else:
        sources_section = "No data"

    # Format boost config section
    boost_lines = [
        f"- **Keywords:** {', '.join(config.keyword_boosts) if config.keyword_boosts else 'None'}",        
        f"- **Recency half-life:** {config.recency_half_life_hours} hours",
    ]
    boost_section = "\n".join(boost_lines)

    # Format eval pass rate (best-effort parse from eval report)
    eval_section = _parse_eval_pass_rate(end_day)

    # Format failures section
    if failures:
        fail_lines = ["| Error Type | Count |", "|------------|-------|"]
        for error_type, count in failures.items():
            fail_lines.append(f"| {error_type} | {count} |")
        failures_section = "\n".join(fail_lines)
    else:
        failures_section = "None"

    # Build full markdown
    lines = [
        f"# Weekly Report — {start_day} to {end_day}",
        "",
        "## Top Sources",
        sources_section,
        "",
        "## Boost Config",
        boost_section,
        "",
        "## Eval Pass Rate",
        eval_section,
        "",
        "## Run Failures",
        failures_section,
        "",
    ]
    content = "\n".join(lines)

    # Write file
    WEEKLY_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    WEEKLY_REPORT_PATH.write_text(content, encoding="utf-8")

    return str(WEEKLY_REPORT_PATH)



def _parse_eval_pass_rate(end_day: str) -> str:
    """Best-effort parse eval pass rate from eval report. Returns 'N/A' if not found."""
    eval_path = Path(f"artifacts/eval_report_{end_day}.md")
    if not eval_path.exists():
        return "N/A"

    try:
        content = eval_path.read_text()
        # Look for pattern like "Pass rate: 85%" or "passed: 17/20"
        # Adjust based on your actual eval report format
        if "pass" in content.lower():
            # Simple extraction — customize to your format
            for line in content.split("\n"):
                if "pass" in line.lower() and "%" in line:
                    return line.strip()
        return "N/A"
    except Exception:
        return "N/A"
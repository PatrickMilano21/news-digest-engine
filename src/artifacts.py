from __future__ import annotations

import html
from datetime import datetime

from src.schemas import NewsItem
from src.scoring import RankConfig
from src.llm_schemas.summary import SummaryResult



def esc(s: str) -> str:
    return html.escape(s, quote=True)

def render_run_header(*, day: str, run: dict | None) -> str:
    if run is None:
        return f"<h2>Digest for {esc(day)}</h2><p><em>No run record found for this day.</em></p>"
    
    run_id = run.get("run_id", "")
    status = run.get("status", "")
    started_at = run.get("started_at", "")
    finished_at = run.get("finished_at", "")

    received = run.get("received", 0)
    after_dedupe = run.get("after_dedupe", 0)
    inserted = run.get("inserted", 0)
    duplicates = run.get("duplicates", 0)

    return f"""
    <h2>Digest for {esc(day)}</h2>
    <div class="run">
      <div><strong>run_id:</strong> {esc(str(run_id))}</div>
      <div><strong>status:</strong> {esc(str(status))}</div>
      <div><strong>started_at:</strong> {esc(str(started_at))}</div>
      <div><strong>finished_at:</strong> {esc(str(finished_at))}</div>
      <div class="counts">
        <span><strong>received:</strong> {received}</span>
        <span><strong>after_dedupe:</strong> {after_dedupe}</span>
        <span><strong>inserted:</strong> {inserted}</span>
        <span><strong>duplicates:</strong> {duplicates}</span>
      </div>
    </div>
    """

def render_why_ranked(expl: dict) -> str:
    topics = expl.get("matched_topics", [])
    kws = expl.get("matched_keywords", [])
    source_weight = expl.get("source_weight", 1.0)
    age_hours = expl.get("age_hours", 0.0)
    recency_decay = expl.get("recency_decay", 1.0)
    relevance = expl.get("relevance", 0.0)
    total_score = expl.get("total_score", 0.0)

    topics_str = ", ".join(esc(str(t)) for t in topics) if topics else "None"
    kw_str = ", ".join(f"{esc(k['keyword'])} (+{k['boost']})" for k in kws) if kws else "None"

    return f"""
    <ul class="why">
      <li><strong>Topics matched:</strong> {topics_str}</li>
      <li><strong>Keyword boosts:</strong> {kw_str}</li>
      <li><strong>Relevance:</strong> {relevance}</li>
      <li><strong>Source weight:</strong> ×{source_weight}</li>
      <li><strong>Recency:</strong> age={age_hours}h decay={recency_decay}</li>
      <li><strong>Total Score:</strong> {total_score}</li>
    </ul>
    """


def render_summary(summary: SummaryResult | None) -> str:
    """Render LLM summary with citations, or refusal reason."""
    if summary is None:
        return ""

    # If refused, show the reason
    if summary.refusal:
        return f"""
        <div class="summary refusal">
          <p>Summary unavailable: {esc(summary.refusal)}</p>
        </div>
        """

    # Build citations list
    citations_html = ""
    if summary.citations:
        citation_items = []
        for c in summary.citations:
            snippet = esc(c.evidence_snippet)
            url = esc(c.source_url)
            citation_items.append(f'<li>"{snippet}" — <a href="{url}">source</a></li>')
        citations_html = f"""
        <div class="citations">
          <strong>Citations:</strong>
          <ul>{"".join(citation_items)}</ul>
        </div>
        """

    # Build summary section
    summary_text = esc(summary.summary or "")
    tags_html = ""
    if summary.tags:
        tags_html = f'<div class="tags">Tags: {", ".join(esc(t) for t in summary.tags)}</div>'

    return f"""
    <div class="summary">
      <p class="summary-text">{summary_text}</p>
      {tags_html}
      {citations_html}
    </div>
    """


def render_item(*, idx: int, item: NewsItem, expl: dict, summary: SummaryResult | None = None) -> str:
    title = esc(item.title)
    url = esc(str(item.url))
    source = esc(item.source)
    published_at = esc(item.published_at.isoformat())

    evidence = item.evidence or ""
    evidence_html = f"<p class='evidence'>{esc(evidence)}</p>" if evidence else ""

    why_html = render_why_ranked(expl)
    summary_html = render_summary(summary)

    return f"""
    <div class="item">
      <div class="rank">#{idx}</div>
      <div class="main">
        <div class="title"><a href="{url}">{title}</a></div>
        <div class="meta">{source} • {published_at}</div>
        {summary_html}
        {evidence_html}
        <div class="whywrap">
          <div class="whytitle">Why ranked</div>
          {why_html}
        </div>
      </div>
    </div>
    """


def render_digest_html(day, run, ranked_items, explanations, cfg, now, top_n, summaries=None) -> str:
    """Render the full digest HTML page.

    Args:
        summaries: Optional list of SummaryResult, one per ranked item.
                   If None, summaries section is omitted.
    """
    header = render_run_header(day=day, run=run)

    # Default to empty list if no summaries provided
    if summaries is None:
        summaries = [None] * len(ranked_items)

    blocks: list[str] = []
    for i, item in enumerate(ranked_items, start=1):
        expl = explanations[i - 1] if i - 1 < len(explanations) else {}
        summary = summaries[i - 1] if i - 1 < len(summaries) else None
        blocks.append(render_item(idx=i, item=item, expl=expl, summary=summary))

    items_html = "\n".join(blocks) if blocks else "<p><em>No items found for this day.</em></p>"

    return f"""<!doctype html>
    <html>
    <head>
    <meta charset="utf-8" />
    <title>Digest {esc(day)}</title>
    <style>
        body {{ font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 24px; }}
        .run {{ padding: 12px; border: 1px solid #ddd; border-radius: 8px; margin-bottom: 16px; }}
        .counts span {{ margin-right: 12px; }}
        .item {{ display: flex; gap: 12px; padding: 12px; border: 1px solid #eee; border-radius: 8px; margin-bottom: 12px; }}
        .rank {{ font-weight: 700; width: 40px; }}
        .title a {{ text-decoration: none; }}
        .meta {{ color: #555; font-size: 12px; margin-top: 4px; }}
        .evidence {{ margin: 10px 0; color: #333; font-style: italic; }}
        .whywrap {{ background: #fafafa; border: 1px solid #eee; padding: 10px; border-radius: 8px; }}
        .whytitle {{ font-weight: 600; margin-bottom: 6px; }}
        .why {{ margin: 0; padding-left: 18px; }}
        .summary {{ background: #f0f7ff; border: 1px solid #cce0ff; padding: 12px; border-radius: 8px; margin: 10px 0; }}
        .summary.refusal {{ background: #fff5f5; border-color: #ffcccc; }}
        .summary-text {{ margin: 0 0 8px 0; }}
        .tags {{ font-size: 12px; color: #666; margin-bottom: 8px; }}
        .citations {{ font-size: 13px; }}
        .citations ul {{ margin: 4px 0; padding-left: 20px; }}
        .citations li {{ margin: 4px 0; }}
    </style>
    </head>
    <body>
    {header}
    <h3>Top {top_n}</h3>
    {items_html}
    </body>
    </html>
    """



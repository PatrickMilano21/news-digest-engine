from __future__ import annotations

import html
from datetime import datetime

from src.schemas import NewsItem
from src.scoring import RankConfig



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

    topics_str = ", ".join(esc(str(t)) for t in topics) if topics else "None"
    kw_str = ", ".join(f"{esc(k['keyword'])} (+{k['boost']})" for k in kws) if kws else "None"

    return f"""
    <ul class="why">
      <li><strong>Topics matched:</strong> {topics_str}</li>
      <li><strong>Keyword boosts:</strong> {kw_str}</li>
      <li><strong>Source weight:</strong> ×{source_weight}</li>
      <li><strong>Recency:</strong> age={age_hours}h decay={recency_decay}</li>
    </ul>
    """

def render_item(*, idx: int, item: NewsItem, expl: dict) -> str:
    title = esc(item.title)
    url = esc(str(item.url))
    source = esc(item.source)
    published_at = esc(item.published_at.isoformat())

    evidence = item.evidence or ""
    evidence_html = f"<p class='evidence'>{esc(evidence)}</p>" if evidence else ""

    why_html = render_why_ranked(expl)

    return f"""
    <div class="item">
      <div class="rank">#{idx}</div>
      <div class="main">
        <div class="title"><a href="{url}">{title}</a></div>
        <div class="meta">{source} • {published_at}</div>
        {evidence_html}
        <div class="whywrap">
          <div class="whytitle">Why ranked</div>
          {why_html}
        </div>
      </div>
    </div>
    """


def render_digest_html(day, run, ranked_items, explanations, cfg, now, top_n) -> str:
    header = render_run_header(day=day, run=run)

    blocks: list[str] = []
    for i, item in enumerate(ranked_items, start=1):
        expl = explanations[i - 1] if i - 1 < len(explanations) else {}
        blocks.append(render_item(idx=i, item=item, expl=expl))

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
        .evidence {{ margin: 10px 0; color: #333; }}
        .whywrap {{ background: #fafafa; border: 1px solid #eee; padding: 10px; border-radius: 8px; }}
        .whytitle {{ font-weight: 600; margin-bottom: 6px; }}
        .why {{ margin: 0; padding-left: 18px; }}
    </style>
    </head>
    <body>
    {header}
    <h3>Top {top_n}</h3>
    {items_html}
    </body>
    </html>
    """



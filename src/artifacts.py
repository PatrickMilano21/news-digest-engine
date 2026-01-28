"""Generate email-safe digest HTML artifacts.

These artifacts are static HTML files saved to artifacts/ directory.
They must be:
- Email-client compatible (table layout, inline-friendly CSS)
- Customer-safe (no debug data like run_id, scores, evidence)
- Self-contained (no external resources)
"""
from __future__ import annotations

import html

from src.schemas import NewsItem
from src.scoring import RankConfig
from src.llm_schemas.summary import SummaryResult
from src.ui_constants import Colors, Strings, format_date_short, format_datetime_friendly


def esc(s: str) -> str:
    """HTML-escape a string."""
    return html.escape(s, quote=True)


def render_header(*, day: str, count: int, run: dict | None) -> str:
    """Render digest header (customer-safe, no debug data)."""
    # Format the date nicely
    day_formatted = format_date_short(day + "T00:00:00")

    # Get run timestamp if available
    updated_at = ""
    if run and run.get("finished_at"):
        updated_at = format_datetime_friendly(run["finished_at"])

    status_line = f'<p style="color: {Colors.TEXT_MUTED}; font-size: 14px; margin: 8px 0 0 0;">Last updated {esc(updated_at)}</p>' if updated_at else ""

    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr>
        <td style="padding-bottom: 20px; border-bottom: 1px solid {Colors.BORDER};">
          <h1 style="margin: 0 0 8px 0; font-size: 26px; font-weight: 600; color: {Colors.TEXT_PRIMARY};">
            News Digest — {esc(day_formatted)}
          </h1>
          <p style="color: {Colors.TEXT_SECONDARY}; font-size: 15px; margin: 0;">
            {Strings.stories_count(count)}
          </p>
          {status_line}
        </td>
      </tr>
    </table>
    """


def render_summary_block(summary: SummaryResult | None) -> str:
    """Render summary or refusal banner (customer-safe)."""
    if summary is None:
        return ""

    if summary.refusal:
        return f"""
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top: 12px;">
          <tr>
            <td style="background: {Colors.REFUSAL_BG}; border-left: 3px solid {Colors.REFUSAL_BORDER}; padding: 12px 14px; border-radius: 0 6px 6px 0;">
              <p style="margin: 0; color: {Colors.REFUSAL_TEXT}; font-size: 14px;">
                {Strings.REFUSAL_MESSAGE}
              </p>
            </td>
          </tr>
        </table>
        """

    summary_text = esc(summary.summary or "")

    # Tags
    tags_html = ""
    if summary.tags:
        tags_list = ", ".join(esc(t) for t in summary.tags)
        tags_html = f'<p style="margin: 8px 0 0 0; font-size: 12px; color: {Colors.TEXT_SECONDARY};">{Strings.TOPICS_LABEL} {tags_list}</p>'

    # Citation count (don't show full citations in email - too long)
    citations_html = ""
    if summary.citations:
        citations_html = f'<p style="margin: 6px 0 0 0; font-size: 12px; color: {Colors.TEXT_SECONDARY};">{Strings.sources_label(len(summary.citations))}</p>'

    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top: 12px;">
      <tr>
        <td style="background: {Colors.SUMMARY_BG}; border-left: 3px solid {Colors.SUMMARY_BORDER}; padding: 12px 14px; border-radius: 0 6px 6px 0;">
          <p style="margin: 0 0 4px 0; font-size: 12px; font-weight: 600; color: {Colors.TEXT_SECONDARY}; text-transform: uppercase; letter-spacing: 0.5px;">{Strings.SUMMARY_LABEL}</p>
          <p style="margin: 0; line-height: 1.6; color: {Colors.TEXT_BODY};">{summary_text}</p>
          {tags_html}
          {citations_html}
        </td>
      </tr>
    </table>
    """


def render_item(*, idx: int, item: NewsItem, summary: SummaryResult | None = None) -> str:
    """Render a single item (customer-safe, no debug data)."""
    title = esc(item.title)
    url = esc(str(item.url))
    source = esc(item.source)
    pub_date = format_date_short(item.published_at.isoformat())

    summary_html = render_summary_block(summary)

    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 16px;">
      <tr>
        <td style="border: 1px solid {Colors.BORDER}; border-radius: 8px; padding: 16px; background: #fff;">
          <p style="margin: 0 0 6px 0; font-size: 17px; font-weight: 600; line-height: 1.4;">
            <a href="{url}" style="color: {Colors.TEXT_PRIMARY}; text-decoration: none;">{title}</a>
          </p>
          <p style="margin: 0; color: {Colors.TEXT_META}; font-size: 13px;">
            {source} · {pub_date}
          </p>
          {summary_html}
        </td>
      </tr>
    </table>
    """


def render_digest_html(day, run, ranked_items, explanations, cfg, now, top_n, summaries=None) -> str:
    """Render email-safe digest HTML.

    Args:
        day: Date string (YYYY-MM-DD)
        run: Run record dict (or None)
        ranked_items: List of NewsItem objects
        explanations: List of explanation dicts (ignored - debug data)
        cfg: RankConfig (ignored - debug data)
        now: Current datetime (ignored)
        top_n: Number of items
        summaries: Optional list of SummaryResult, one per ranked item.

    Returns:
        Complete HTML document string.
    """
    # Default to empty list if no summaries provided
    if summaries is None:
        summaries = [None] * len(ranked_items)

    header = render_header(day=day, count=len(ranked_items), run=run)

    # Render items
    items_html_parts: list[str] = []
    for i, item in enumerate(ranked_items):
        summary = summaries[i] if i < len(summaries) else None
        items_html_parts.append(render_item(idx=i + 1, item=item, summary=summary))

    items_html = "\n".join(items_html_parts) if items_html_parts else f"""
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr>
        <td style="text-align: center; padding: 40px 20px; color: {Colors.TEXT_SECONDARY};">
          <p>{Strings.NO_STORIES}</p>
        </td>
      </tr>
    </table>
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>News Digest — {esc(day)}</title>
  <style>
    body {{
      font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      margin: 0;
      padding: 24px;
      background: #f5f5f5;
    }}
    .container {{
      max-width: 600px;
      margin: 0 auto;
      background: #fff;
      padding: 24px;
      border-radius: 8px;
    }}
    a {{ color: {Colors.LINK}; }}
    a:hover {{ color: {Colors.LINK_HOVER}; }}
  </style>
</head>
<body>
  <div class="container">
    {header}
    <div style="margin-top: 24px;">
      {items_html}
    </div>
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top: 24px; border-top: 1px solid {Colors.BORDER};">
      <tr>
        <td style="padding-top: 16px; text-align: center; color: {Colors.TEXT_MUTED}; font-size: 12px;">
          <p style="margin: 0;">{Strings.GENERATED_BY}</p>
        </td>
      </tr>
    </table>
  </div>
</body>
</html>
"""

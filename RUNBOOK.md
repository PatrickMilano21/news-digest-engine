# RUNBOOK — News Digest Engine

Operational guide for running, monitoring, and debugging the News Digest Engine.

---

## 1. What This System Does

The News Digest Engine ingests RSS feeds, normalizes and deduplicates items, ranks them deterministically, optionally summarizes them with an LLM (with grounding validation and caching), and produces daily HTML digests with evaluation reports.

```
RSS Feeds → Ingest → Normalize/Dedupe → Rank → LLM Summarize → HTML Digest + Eval Report
```

**Inputs:** RSS feed URLs (configured in the daily job)
**Outputs:** `artifacts/digest_YYYY-MM-DD.html`, `artifacts/eval_report_YYYY-MM-DD.md`

---

## 2. How to Run the Daily Job

### Command

```powershell
make run DATE=2026-01-23
```

### What Happens

1. **Ingest phase:** Fetches RSS feeds, normalizes URLs/titles, deduplicates items
2. **Digest phase:** Ranks top items, calls LLM for summaries (with cache), validates grounding
3. **Artifacts:** Writes digest HTML and eval report markdown

### Idempotency

- **First run for a date:** Full pipeline executes, run record created with status `ok`
- **Repeat run for same date:** Skipped if successful run already exists (idempotent)
- **To force re-run:** Delete the run record from the database or use a different date

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `NEWS_DB_PATH` | SQLite database path | `./data/news.db` |
| `OPENAI_API_KEY` | LLM API key (required for summaries) | None (LLM disabled if unset) |

---

## 3. Where Artifacts Live

| Artifact | Path | Description |
|----------|------|-------------|
| Daily Digest | `artifacts/digest_YYYY-MM-DD.html` | Ranked news items with summaries and explanations |
| Eval Report | `artifacts/eval_report_YYYY-MM-DD.md` | Ranking + summary quality eval results |
| Database | `data/news.db` | SQLite with items, runs, cache, feedback |

### Artifact Retention

Artifacts are overwritten on re-runs for the same date. No automatic cleanup — manual deletion required for old artifacts.

---

## 4. How to Inspect a Run

### Step 1: Get the Latest Run

```bash
curl http://localhost:8000/runs/latest
```

Returns:
```json
{
  "run_id": "abc123...",
  "status": "ok",
  "started_at": "2026-01-23T10:00:00+00:00",
  "received": 150,
  "inserted": 142,
  "duplicates": 8
}
```

### Step 2: Get Full Debug Details

```bash
curl http://localhost:8000/debug/run/{run_id}
```

Returns:
```json
{
  "run_id": "abc123...",
  "run_type": "ingest",
  "status": "ok",
  "started_at": "...",
  "finished_at": "...",
  "counts": {
    "received": 150,
    "after_dedupe": 142,
    "inserted": 140,
    "duplicates": 2
  },
  "llm_stats": {
    "cache_hits": 8,
    "cache_misses": 2,
    "cache_hit_rate": 80.0,
    "total_cost_usd": 0.0012,
    "saved_cost_usd": 0.0048,
    "total_latency_ms": 3200
  },
  "failures_by_code": {
    "GROUNDING_FAIL": 1
  },
  "artifact_paths": {
    "digest": "artifacts/digest_2026-01-23.html",
    "eval_report": "artifacts/eval_report_2026-01-23.md"
  }
}
```

### Field Reference

| Field | Meaning |
|-------|---------|
| `counts.received` | Items fetched from RSS feeds |
| `counts.after_dedupe` | Items after Python-level deduplication |
| `counts.inserted` | New items written to database |
| `counts.duplicates` | Items already in database (skipped) |
| `llm_stats.cache_hits` | Summaries served from cache |
| `llm_stats.cache_misses` | Fresh LLM API calls made |
| `llm_stats.cache_hit_rate` | Percentage of cache hits |
| `llm_stats.total_cost_usd` | Actual LLM spend this run |
| `llm_stats.saved_cost_usd` | Money saved via cache |
| `llm_stats.total_latency_ms` | Total LLM wall-clock time |
| `failures_by_code` | Error counts grouped by failure code |

---

## 5. Common Failure Modes + Fixes

| Symptom | Likely Cause | Where to Look | Fix |
|---------|--------------|---------------|-----|
| Many `NO_EVIDENCE` | RSS feeds returning thin content | `failures_by_code` in debug endpoint | Add full-article fetch or use richer feeds |
| Many `GROUNDING_FAIL` | LLM hallucinating citations | Eval report, `failures_by_code` | Tighten prompt constraints, lower temperature |
| High `total_cost_usd` | Cache disabled or many misses | `llm_stats.cache_hit_rate` | Check cache key logic, verify evidence normalization |
| Low `cache_hit_rate` | Evidence text changing between runs | Compare cache keys | Ensure evidence is stable/normalized |
| Empty digest | Ingest failed or no items for date | Run status, `counts.received` | Check RSS feed URLs, verify date has items |
| `LLM_DISABLED` refusals | `OPENAI_API_KEY` not set | Environment variables | Set the API key |
| `LLM_API_FAIL` | OpenAI API error | Logs (stdout) | Check API status, retry, verify key |
| `LLM_PARSE_FAIL` | LLM returned malformed JSON | Logs | May need prompt adjustment |
| Status `error` | Pipeline exception | `error_type`, `error_message` in run | Read error message, check logs |

### Failure Codes Reference

| Code | Meaning |
|------|---------|
| `NO_EVIDENCE` | Item had no evidence text to summarize |
| `GROUNDING_FAIL` | LLM citation didn't match evidence |
| `LLM_DISABLED` | No API key configured |
| `LLM_API_FAIL` | OpenAI API call failed |
| `LLM_PARSE_FAIL` | LLM response wasn't valid JSON |
| `PIPELINE_ERROR` | General pipeline failure |

---

## 6. Safe Recovery Steps

### Re-run the Same Date

If a run failed or produced bad output:

1. Check the error via `/debug/run/{run_id}`
2. Fix the underlying issue (feed URL, API key, etc.)
3. Delete the failed run record (or let idempotency skip if status was `error`)
4. Re-run: `make run DATE=YYYY-MM-DD`

### Disable LLM Temporarily

If LLM is causing issues and you need a digest without summaries:

1. Unset `OPENAI_API_KEY`: `$env:OPENAI_API_KEY = $null`
2. Run the pipeline — summaries will show `LLM_DISABLED` refusals
3. Digest will render without summaries

### Inspect Before Changing Prompts

Before modifying LLM prompts:

1. Run `make eval DATE=YYYY-MM-DD` to get baseline eval scores
2. Review `artifacts/eval_report_YYYY-MM-DD.md` for current failure breakdown
3. Make prompt changes
4. Re-run eval and compare pass rates

### Database Recovery

If database is corrupted:

1. Stop the server: `Ctrl+C`
2. Backup current DB: `copy data\news.db data\news.db.bak`
3. Delete and restart (will recreate tables): `del data\news.db`
4. Re-ingest historical dates as needed

---

## 7. Alerts to Watch (Conceptual)

These are conditions that indicate problems. No automated alerting is configured — manual monitoring required.

### Error Spike

**Trigger:** Sudden increase in `PIPELINE_ERROR` or `LLM_API_FAIL` counts
**Meaning:** Something in the pipeline or external API is broken
**Action:** Check `/debug/run/{run_id}` for error details, review logs

### Cost Spike

**Trigger:** `llm_stats.total_cost_usd` significantly higher than baseline
**Meaning:** Cache is missing or prompt got longer
**Action:** Check `cache_hit_rate`, compare evidence sizes, review prompt changes

### Empty Evidence Spike

**Trigger:** High percentage of `NO_EVIDENCE` failures
**Meaning:** RSS feeds are returning items without content
**Action:** Review feed sources, consider adding full-article fetch

### Cache Regression

**Trigger:** `cache_hit_rate` drops unexpectedly (e.g., from 80% to 20%)
**Meaning:** Cache keys are changing when they shouldn't
**Action:** Compare cache key computation, check evidence normalization

### Grounding Failures

**Trigger:** Increase in `GROUNDING_FAIL` count
**Meaning:** LLM is hallucinating or not following citation rules
**Action:** Review prompt constraints, check model version, consider temperature=0

---

## 8. Useful Commands

```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run tests
make test

# Start dev server (port 8000, auto-reload)
make dev

# Daily pipeline for a specific date
make run DATE=2026-01-23

# Run evaluation harness
make eval DATE=2026-01-23

# Query endpoints
curl http://localhost:8000/health
curl http://localhost:8000/runs/latest
curl http://localhost:8000/debug/run/{run_id}

# View UI
http://localhost:8000/ui/date/2026-01-23
```

---

## 9. Contacts

**Repository:** `news-digest-engine`
**Owner:** Patrick Milano

---

---

## 10. Web UI

### Home Page

```
http://localhost:8000/
```

Three tabs:
- **Digests**: Paginated list of dates with star ratings
- **Runs**: Recent pipeline runs with status
- **Debug**: Links to debug tools

### Date Page

```
http://localhost:8000/ui/date/{date}
```

Shows ranked items for a date with:
- Title and source
- LLM summary (if available)
- "Why Ranked" explanation
- Thumbs up/down feedback buttons

### Item Page

```
http://localhost:8000/ui/item/{id}
```

Single item detail with back-link to date page.

---

## 11. Feedback System

### Run Feedback (Star Ratings)

```bash
curl -X POST http://localhost:8000/feedback/run \
  -H "Content-Type: application/json" \
  -d '{"run_id": "abc123", "rating": 4}'
```

- Ratings 1-5 stars
- Saved to `run_feedback` table
- Displayed on home page

### Item Feedback (Useful/Not Useful)

```bash
curl -X POST http://localhost:8000/feedback/item \
  -H "Content-Type: application/json" \
  -d '{"run_id": "abc123", "item_url": "https://...", "useful": true}'
```

- Saved to `item_feedback` table
- Displayed on date page

---

## 12. Failed Sources Debugging

When a run has failures, you can now see exactly which feeds failed:

```bash
curl http://localhost:8000/debug/run/{run_id}
```

Response includes:
```json
{
  "failures_by_code": {"PARSE_ERROR": 1},
  "failed_sources": {"PARSE_ERROR": ["fixtures/feeds/broken_feed.xml"]}
}
```

This helps identify which specific RSS feed or fixture file caused the error.

---

## 13. Direct Database Queries

For advanced debugging, open SQLite directly:

```powershell
sqlite3 data/news.db
```

**Quick queries:**
```sql
-- Items by date
SELECT substr(published_at, 1, 10) as day, COUNT(*) FROM news_items GROUP BY day ORDER BY day DESC;

-- Recent runs
SELECT run_id, substr(started_at, 1, 10) as day, status, received, inserted FROM runs ORDER BY started_at DESC LIMIT 10;

-- Run failures
SELECT * FROM run_failures ORDER BY created_at DESC LIMIT 10;

-- Cached summaries
SELECT cache_key, model_name, cost_usd, latency_ms FROM summary_cache LIMIT 10;

-- Exit
.quit
```

---

*Last updated: Day 20 (2026-01-25)*

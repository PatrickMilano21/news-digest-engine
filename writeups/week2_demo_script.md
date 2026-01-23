# Week 2 Checkpoint Demo — News Digest Engine

## 0) One-liner
Deterministic news ingestion + ranking + artifacts with eval-driven regression protection and operator-grade run summaries.

## 1) Demo commands
```bash
make test                    # 101 tests pass
make run DATE=2026-01-20     # creates run record + digest artifact
make eval DATE=2026-01-20    # runs eval harness, writes report
```

## 2) What the system does (flow)
```
RSS ingest → normalize/dedupe → rank → digest artifact → run record → eval report → debug endpoints
```

Live endpoints:
- `GET /ui/date/2026-01-20` — server-rendered item list with scores
- `GET /digest/2026-01-20` — HTML artifact with "Why ranked" explanations
- `GET /runs/latest` — last run metadata
- `GET /debug/run/{run_id}` — counts, failures by code, artifact paths

## 3) Ranking rules (what drives ordering)
```python
score = (topic_matches + keyword_boosts) × source_weight × recency_decay
```

- **Recency decay:** `1 / (1 + age_hours / half_life)` — fresher items score higher
- **Source weights:** configurable per-source multiplier (e.g., reuters: 1.5)
- **Keyword/topic boosts:** additive score for matching terms in title/evidence
- **Tie-breaks:** score desc → published_at desc → original index asc (deterministic)

## 4) Evals (how regressions are caught)
- **Golden set:** 50 fixture-driven test cases with expected rankings
- **Comparison:** expected order vs actual order per item
- **Output:** `artifacts/eval_report_2026-01-20.md` with pass/fail + diffs
- **Failure taxonomy:** error codes (FETCH_TIMEOUT, RATE_LIMITED, PARSE_ERROR, etc.) surfaced in run_failures table and debug endpoints

## 5) Operability (how you debug it fast)
- `/runs/latest` — quick health check: status, counts, timestamps
- `/debug/run/{run_id}` — deep dive: counts, failures_by_code breakdown, artifact_paths
- `X-Request-ID` header on every response for log correlation
- Structured JSON logging via `log_event()` for all operations
- Audit logs table with PII redaction for compliance

## 6) What improved this week (3 bullets)
- **Eval harness with golden set:** 50-case regression suite catches ranking drift automatically; generates markdown reports with pass/fail breakdown
- **Server-rendered UI + debug endpoints:** `/ui/date/{day}` shows ranked items with scores; `/debug/run/{id}` exposes failure taxonomy and artifact paths for fast diagnosis
- **Enterprise posture:** PII redaction layer (emails/phones), audit logging (RUN_STARTED/FINISHED events), weekly aggregate reports (top sources, failure rates)

## 7) Tradeoffs (2 bullets)
- **Fixture-driven, not live feeds:** Eval harness uses deterministic fixtures; real RSS ingestion exists but isn't the reliability focus yet. This keeps tests fast and reproducible.
- **Config not snapshotted per-run:** Weekly report shows current RankConfig, not historical. A future iteration would store config with each run for full audit trail.

## 8) Next reliability target (1-2 bullets)
- **MCP as intelligence boundary:** Week 3 adds LLM grounding with citations, using MCP tools as the constrained interface between deterministic pipeline and non-deterministic inference.
- **Config snapshots:** Store RankConfig per run to enable historical "why did this rank differently last week?" queries.

---

## Screenshots
Save to `writeups/week2_screenshots/`:
1. `ui_date_view.png` — `/ui/date/2026-01-20`
2. `eval_report.png` — `artifacts/eval_report_2026-01-20.md`
3. `debug_run_response.png` — `/debug/run/{run_id}` JSON response

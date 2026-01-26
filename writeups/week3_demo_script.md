# Week 3 Checkpoint Demo — News Digest Engine

**Duration:** 4-5 minutes
**Audience:** Technical interviewers, engineering managers
**Demo Date:** 2026-01-24
**Run ID:** `8aa331aedc764623a08693a92bf1c831`

---

## 1. What This System Does (30 seconds)

"This is a news digest engine: RSS ingest → normalize/dedupe → deterministic rank → optional LLM summaries → daily HTML digest. Evals and debug endpoints are first-class outputs."

```
RSS Feeds → Ingest → Normalize/Dedupe → Rank → LLM Summarize → HTML Digest
                                                      ↓
                                              Evals + Debug Endpoints
```

**Key point:** The LLM is an optional stage behind a strict contract. The system still completes if it refuses.

---

## 2. Why This Is Production-Shaped (30 seconds)

"It's production-shaped because the core is deterministic, every change is eval-gated, every run is observable via a single debug payload, and the LLM sits behind a strict safety boundary."

| Property | How It's Enforced |
|----------|-------------------|
| **Deterministic core** | Same inputs → same ranking, always |
| **Eval gate** | Ranking + summary evals run automatically in pipeline |
| **Observable runs** | Single debug endpoint tells the full run story |
| **Safe LLM boundary** | Contract-enforced or refused — no silent failures |

---

## 3. LLM Safety Boundary (60-75 seconds)

### The Contract

"LLM contract: either summary+citation or refusal—never both. Citations are validated against evidence; if they don't match, we fail the whole result as grounding failure. So we refuse rather than guess."

- **(summary + citations)** — grounded output with verifiable quotes
- **OR (refusal)** — explicit reason code, no output

Never both. Never neither.

### Grounding Validation

Evidence snippets must be verifiably present in the source evidence (strict match). If validation fails, we reject the entire result with `GROUNDING_FAIL`.

### Common Refusal Codes

| Refusal Code | Meaning |
|--------------|---------|
| `NO_EVIDENCE` | Item had no evidence text to summarize |
| `GROUNDING_FAIL` | LLM citation didn't match evidence |
| `LLM_DISABLED` | No API key configured |
| `LLM_API_FAIL` | OpenAI API error (timeout, rate limit, network) |
| `LLM_PARSE_FAIL` | Response not valid JSON after retry |

**Key point:** Users see a clear explanation, not a bad guess.

---

## 4. Quality Enforcement (45-60 seconds)

"Quality: ranking and summary eval suites run automatically and write an eval report artifact. If something regresses, we see it immediately."

### Eval Suites

- **Ranking evals** — verify deterministic ordering behavior
- **Summary evals** — verify citation validity and refusal conditions

Both run automatically with every pipeline execution. No manual QA step.

### Output

Every run produces `artifacts/eval_report_2026-01-24.md`:

```
Ranking Evals: 50 passed, 0 failed
Summary Evals: 32 passed, 0 failed
Overall: PASS
```

The eval report shows exactly what broke; the run is marked accordingly.

---

## 5. Debug Story (60-75 seconds)

"Debugging: here's /debug/run/{run_id}. Counts, cache, cost, failures, artifact paths. I can answer user tickets from this payload without opening code."

### The Debug Endpoint

`GET /debug/run/8aa331aedc764623a08693a92bf1c831`

```json
{
  "run_id": "8aa331aedc764623a08693a92bf1c831",
  "status": "ok",
  "counts": {
    "received": 5,
    "after_dedupe": 5,
    "inserted": 0,
    "duplicates": 5
  },
  "llm_stats": {
    "cache_hits": 5,
    "cache_misses": 0,
    "cache_hit_rate": 100.0,
    "total_cost_usd": 0.0,
    "saved_cost_usd": 0.000743
  },
  "failures_by_code": {},
  "failed_sources": {},
  "artifact_paths": {
    "digest": "artifacts/digest_2026-01-24.html",
    "eval_report": "artifacts/eval_report_2026-01-24.md"
  }
}
```

**Key point:** `saved_cost_usd` shows avoided spend via caching. Debug surface is designed so on-call can diagnose from a single JSON payload.

### Answering a User Ticket Without Reading Code

**Ticket:** "Why did summaries stop halfway through today's digest?"

1. Open `/debug/run/{run_id}`
2. Check `failures_by_code` — is there a spike in `LLM_API_FAIL` / `GROUNDING_FAIL` / `NO_EVIDENCE`?
3. Check `llm_stats.cache_hit_rate` — did it drop, and did model/version change between runs?
4. Check `failed_sources` — did a specific feed fail?

Answer in 30 seconds, no code required.

*(Note: Week 4 adds `COST_BUDGET_EXCEEDED` for spend limits.)*

---

## 6. Failure Demo (30 seconds)

"Failure example: UI shows NO_EVIDENCE; debug shows failures_by_code. Operator action is feed quality or full-article fetch."

**Scenario:** An item refuses summarization.

1. **UI shows:** "Refusal: NO_EVIDENCE — Item had no evidence text to summarize"
2. **Debug endpoint shows:** `"failures_by_code": {"NO_EVIDENCE": 1}`
3. **Operator action:** Check if feed is returning thin content, consider full-article fetch

The system didn't guess. It told us exactly what went wrong and where.

---

## 7. Tradeoffs + Next Step (30 seconds)

"Tradeoffs: RSS snippets + SQLite + strict refusals. Next step: full-article fetch behind a flag and auth/RBAC on debug surfaces."

### Tradeoffs I Accepted

- **RSS snippets instead of full articles** — faster, but less context for LLM
- **SQLite instead of production DB** — simpler, not horizontally scalable
- **Strict refusals over "best effort"** — safer, some items show no summary

### Next Production Step

- Full-article fetching behind feature flag
- Per-user RankConfig customization (requires auth)
- Auth/RBAC for debug surfaces

---

## Demo Commands

```powershell
# Run the full pipeline
make run DATE=2026-01-24

# View the digest UI
http://localhost:8001/ui/date/2026-01-24

# Debug a specific run
curl http://localhost:8001/debug/run/8aa331aedc764623a08693a92bf1c831
```

---

## Sanity Check Questions

Can I answer these without opening code?

1. **Why did one item refuse summarization?**
   → UI shows refusal reason; debug endpoint shows `failures_by_code`

2. **What would I check if cost doubled tomorrow?**
   → `llm_stats.cache_hit_rate` — if it dropped, cache keys changed

3. **How do I rerun safely?**
   → `make run` is idempotent; use `--force` to override

---

## Appendix: Schema Reference

### SummaryResult Contract

```python
class SummaryResult(BaseModel):
    summary: str | None = None
    tags: list[str] = []
    citations: list[Citation] = []
    confidence: float | None = None
    refusal: str | None = None

# Validator enforces: (summary + citations) XOR refusal
```

### Citation Structure

```python
class Citation(BaseModel):
    source_url: str
    evidence_snippet: str  # Must match source evidence
```

---

*Demo Date: 2026-01-24*
*Run ID: 8aa331aedc764623a08693a92bf1c831*
*Status: Day 21 Complete*

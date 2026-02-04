# Future Work — News Digest Engine

Planned enhancements organized by theme.

---

## Weight Learning Enhancements

### Simulate Weight Evolution
Run a multi-day simulation to visualize how weights change over time with accumulated feedback.

```bash
make simulate-weights DAYS=30
# Seeds random feedback patterns, runs weight updates day-by-day
# Outputs: weight progression chart, final weights, artifact per day
```

**Use case:** Demo the learning loop, test edge cases, validate convergence behavior.

### TF-IDF AI Score (Milestone 3c)
Content similarity boost using TF-IDF vectors and cosine similarity to positively-labeled historical items. Surfaces articles similar to ones the user previously liked.

### Freshness Mix (Post-3c)
Add a freshness component so each digest includes at least a couple of novel items even if similarity scores are high. This prevents repetitive topics and keeps discovery healthy.

---

## User Personalization

### Per-User RankConfig
Allow users to customize ranking preferences:
- Topic weights
- Keyword boosts
- Source trust levels

**Requires:** User authentication (OAuth or simple sessions), user preferences table.

### Per-User Feedback
Currently feedback is global. With users:
- Each user rates independently
- Aggregate for overall signal
- Personalized weight learning per user

**Note:** `weight_snapshots` table already has `user_id` column for this.

---

## UI Improvements

- **Dark mode** — respect system preference
- **Mobile responsive** — better small-screen layout
- **Search/filter** — find items by keyword or date range
- **Digest comparison** — compare two dates side-by-side
- **Export** — download as PDF or markdown

---

## LLM Improvements

- **Model selection** — GPT-4 vs GPT-3.5 cost/quality tradeoff
- **Batch summarization** — multiple items per API call
- **Citation verification** — verify citations appear in evidence

---

## Memory & Retrieval (Vector Search)

### When to Add Embeddings (Robustness Criteria)
- **Data volume** — only worth it once outcomes per user are large enough
- **Quality gap** — add vectors only if tag-based retrieval misses key context
- **Evaluation** — require an offline eval showing better suggestions
- **Latency/cost** — embeddings add write cost and query latency; measure impact
- **Fallbacks** — keep tag-based search as a reliable baseline
- **Privacy/durability** — decide retention, compaction, and redaction policies

**Rule of thumb:** v1 tag-based only, v2 add embeddings if quality gap is proven, v3 add compaction + hybrid search.

### OpenClaw-Inspired Robustness (Map to v2/v3)

**Memory indexing (v2 groundwork):**
- Passage: "File type: Markdown only (`MEMORY.md`, `memory/**/*.md`)."
- Passage: "Watcher ... marks the index dirty (debounce 1.5s)."
- Passage: "Reindex triggers: ... embedding provider/model + endpoint fingerprint + chunking params."
- Mapping:
  - Track index metadata (provider/model/chunking params) and force reindex when they change.
  - Use a "dirty" flag + debounce to avoid re-embedding on every write.
  - Store vector index per-agent/user to keep retrieval scoped and fast.

**Hybrid search merge (v2 retrieval quality):**
- Passage: "Vector similarity ... BM25 keyword relevance."
- Passage: "`textScore = 1 / (1 + max(0, bm25Rank))`."
- Passage: "`finalScore = vectorWeight * vectorScore + textWeight * textScore`."
- Mapping:
  - Build candidate pools from both vector and BM25; union by ID.
  - Normalize BM25 into a 0..1-ish score before blending.
  - Normalize weights to sum to 1.0 so they behave as percentages.
  - Add fallbacks: BM25-only if embeddings fail; vector-only if FTS unavailable.

**Hooks (v3 reliability + automation):**
- Passage: "Hooks provide an extensible event-driven system."
- Passage: "Hooks are automatically discovered from directories."
- Mapping:
  - Add event hooks for accept/reject to update profiles + log outcomes.
  - Schedule compaction and global pattern aggregation as background hooks.
  - Keep hooks small, explicit, and auditable (no hidden side effects).

**Takeaways to make our system more robust:**
- Always store index metadata and reindex on any embedding/chunking change.
- Debounce indexing; sync asynchronously to avoid latency spikes.
- Blend retrieval signals only after score normalization and candidate union.
- Use explicit fallbacks so retrieval never hard-fails.
- Automate compaction/pattern jobs with auditable hooks (not inline requests).

---

## Bugs to Investigate

- **`make run DATE=2026-01-15` produces 0 items** — Run record exists (`already_ok`) but no news_items in DB. `--force` flag not wired through Makefile. Even after re-running, `count=0` on digest. May be a data issue (items were never ingested) or an idempotency check preventing re-ingest. Needs investigation.
- **Fixture mode date mismatch** — `make run DATE=2026-02-04 --mode fixtures` creates a run record for 2026-02-04, but items get `published_at` from the fixture XML (2026-01-24). Home page redirects to `/ui/date/2026-02-04` which 404s because items are actually under 2026-01-24. Fix: either override `published_at` to match `--date`, or redirect to the date that has items.

---

## Automation

- **Add advisor to overnight batch script** — `scripts/overnight_local.bat` already runs daily ingest. Add `python -m jobs.run_advisor --all-users` as a step. Wire into Windows Task Scheduler alongside existing daily run.
- **Extend verifier MCP with `ui_smoke_suggestions`** — Automated smoke test for suggestions page: auth check, empty state, seed suggestion, verify card renders, accept/reject, verify resolution. Add to `mcp-servers/verifier/server.py` alongside existing `ui_smoke`.

---

## Production Readiness

- [ ] Environment configuration (staging vs prod)
- [ ] Database backups
- [ ] Error alerting (email/Slack on failures)
- [ ] Rate limiting on public endpoints
- [ ] Dockerfile for containerized deployment
- [ ] CI/CD pipeline (GitHub Actions)

---

## Performance

- **Database indexing** — indexes for common queries
- **Caching layer** — Redis for frequent data
- **Async feed fetching** — parallel RSS fetches
- **Cursor pagination** — for large datasets

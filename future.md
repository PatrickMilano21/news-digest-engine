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

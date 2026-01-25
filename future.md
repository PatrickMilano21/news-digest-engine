# Future Work — News Digest Engine

This document tracks planned future enhancements and improvements.

---

## Task #11: Per-user RankConfig Customization via UI

**Priority:** Medium
**Complexity:** High (requires auth)

### Description
Allow users to customize ranking preferences through the UI:
- Adjust topic weights
- Add/remove keywords
- Configure source trust levels
- Save preferences per user

### Prerequisites
1. **User authentication** — login system (OAuth, JWT, or simple sessions)
2. **User table** — store user accounts
3. **User preferences table** — store per-user RankConfig

### Implementation Steps
1. Add user authentication (consider OAuth for simplicity)
2. Create `users` table with basic profile
3. Create `user_preferences` table linking user_id to RankConfig JSON
4. Add UI for editing preferences (form with topic/keyword/source inputs)
5. Modify ranking endpoints to accept user context
6. Load user's RankConfig when rendering digests

### Database Changes
```sql
CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    email TEXT UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE user_preferences (
    user_id TEXT PRIMARY KEY REFERENCES users(user_id),
    rank_config_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### Considerations
- Start with simple email/password or OAuth (Google)
- Default RankConfig for anonymous users
- Allow "reset to defaults" option
- Consider A/B testing different default configs

---

## Per-user Feedback

**Priority:** Low
**Depends on:** Task #11 (user auth)

### Description
Currently feedback is global (one rating per digest). With users:
- Each user can rate each digest
- Aggregate ratings for overall quality signal
- Use feedback to improve ranking over time

### Database Changes
```sql
-- Modify existing tables
ALTER TABLE run_feedback ADD COLUMN user_id TEXT;
ALTER TABLE item_feedback ADD COLUMN user_id TEXT;

-- Update unique constraints
-- UNIQUE(run_id, user_id) instead of UNIQUE(run_id)
```

---

## UI Improvements

**Priority:** Medium
**Complexity:** Low-Medium

### Planned Enhancements
1. **Dark mode** — respect system preference
2. **Mobile responsive** — better layout on small screens
3. **Search/filter** — find items by keyword or date range
4. **Digest comparison** — compare two dates side-by-side
5. **Export** — download digest as PDF or markdown

---

## LLM Improvements

**Priority:** Medium
**Complexity:** Medium

### Planned Enhancements
1. **Model selection** — allow choosing GPT-4 vs GPT-3.5 based on cost/quality tradeoff
2. **Batch summarization** — summarize multiple items in one API call
3. **Summary quality evals** — automated checks for summary accuracy
4. **Citation verification** — verify citations actually appear in evidence

---

## Production Readiness

**Priority:** High
**Complexity:** Medium

### Checklist
- [ ] Environment configuration (staging vs prod)
- [ ] Database backups
- [ ] Error alerting (email/Slack on failures)
- [ ] Rate limiting on public endpoints
- [ ] Health check endpoint for monitoring
- [ ] Dockerfile for containerized deployment
- [ ] CI/CD pipeline (GitHub Actions)

---

## Performance Optimization

**Priority:** Low
**Complexity:** Medium

### Potential Improvements
1. **Database indexing** — add indexes for common queries
2. **Caching layer** — Redis for frequently accessed data
3. **Async feed fetching** — parallel RSS fetches
4. **Pagination optimization** — cursor-based pagination for large datasets

---

## Notes

- Task #11 is the main blocker for several other features
- Focus on production readiness before adding more features
- UI improvements can be done incrementally
- LLM improvements should wait until core features are stable

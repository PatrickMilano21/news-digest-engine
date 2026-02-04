# Memory Architecture — Config Advisor Agent

Designing an intelligent, cost-efficient memory system that knows users deeply.

**Influences:**
- [claude-mem](https://github.com/thedotmack/claude-mem) — Token-efficient 3-layer retrieval
- [OpenClaw Docs](https://docs.openclaw.ai/) — Session and context management
- [OpenClaw GitHub](https://github.com/openclaw/openclaw) — Gateway architecture patterns
- [Clawdbot Memory](clawd.memory.md) — Two-layer storage, hybrid search, compaction

---

## Design Principles

1. **Search Over Injection** — Don't stuff context with everything. Agent searches for what's relevant.

2. **Filter Before Fetching** — Use lightweight search first, expand only what matters. 10x token savings.

3. **Progressive Disclosure** — 3 layers: snippets → timeline → full detail. Agent controls depth.

4. **Persistence Over Session** — Important information survives in DB/files, not just conversation history.

5. **Hybrid Over Pure** — Combine tag-based (exact) + semantic (meaning) search for best results.

6. **Compute Once, Query Fast** — Pre-aggregate patterns into profiles. Raw data stays for audit, profiles serve queries.

---

## Storage Architecture (3 Layers)

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 1: Raw Events (Database)                                 │
│  Table: suggestion_outcomes                                      │
│                                                                  │
│  ├─ Every accept/reject with full context                       │
│  ├─ Append-only, never delete (audit trail)                     │
│  ├─ Cheap to store, expensive to query in bulk                  │
│  └─ Source of truth for all derived data                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ (computed on write or nightly)
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 2: Computed Profiles (Database)                          │
│  Table: user_preference_profiles                                 │
│                                                                  │
│  ├─ Aggregated patterns from Layer 1                            │
│  ├─ Source affinities, tag patterns, trend signals              │
│  ├─ Pre-computed = fast retrieval, low tokens                   │
│  └─ Updated incrementally on each outcome                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ (agent writes insights)
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 3: Curated Insights (Markdown)                           │
│  File: .claude/rules/config-advisor/learned-patterns.md         │
│                                                                  │
│  ├─ Agent-written generalizations                               │
│  ├─ Cross-user patterns (anonymized)                            │
│  ├─ "Users who reject X tend to also reject Y"                  │
│  └─ Human-reviewable, version-controlled                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### suggestion_outcomes (Layer 1 - Raw Events)

```sql
CREATE TABLE suggestion_outcomes (
    outcome_id INTEGER PRIMARY KEY,
    suggestion_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,

    -- What was suggested
    suggestion_type TEXT NOT NULL,  -- 'add_topic', 'remove_topic', 'boost_source', 'reduce_source'
    suggestion_value TEXT NOT NULL, -- The TARGET, not numeric weight
                                    -- For topics: the topic name (e.g., "kubernetes")
                                    -- For sources: the source name (e.g., "techcrunch")
                                    -- Computed: target_key if target_key else suggested_value

    -- What happened
    outcome TEXT NOT NULL,          -- 'accepted', 'rejected', 'expired', 'superseded'
    user_reason TEXT,               -- Optional: why user accepted/rejected

    -- Context snapshot (for learning)
    config_before TEXT,             -- JSON: config state when suggested
    config_after TEXT,              -- JSON: config state after (if accepted)
    evidence_summary TEXT,          -- JSON: [{url, title, feedback, reason_tag, item_id?}]
                                    -- Note: url is canonical key, item_id is optional

    -- Metadata
    created_at TEXT NOT NULL,
    decided_at TEXT,

    FOREIGN KEY (suggestion_id) REFERENCES config_suggestions(suggestion_id)
);

-- Indexes for 3-layer retrieval
CREATE INDEX idx_outcomes_user ON suggestion_outcomes(user_id);
CREATE INDEX idx_outcomes_type ON suggestion_outcomes(suggestion_type, outcome);
CREATE INDEX idx_outcomes_date ON suggestion_outcomes(created_at);
```

### user_preference_profiles (Layer 2 - Computed)

```sql
CREATE TABLE user_preference_profiles (
    profile_id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE,

    -- Acceptance rates by suggestion type
    acceptance_stats TEXT NOT NULL,  -- JSON: {type: {accepted, rejected, rate}}

    -- Learned patterns
    patterns TEXT NOT NULL,          -- JSON: {pattern_name: bool/value}

    -- Behavioral signals
    trends TEXT,                     -- JSON: {engagement, stability, velocity}

    -- Metadata
    total_outcomes INTEGER DEFAULT 0,
    last_outcome_at TEXT,
    computed_at TEXT NOT NULL,

    UNIQUE(user_id)
);
```

---

## Retrieval Pattern (3-Layer)

*Inspired by claude-mem's 10x token savings approach*

**Implementation note:** The 3 tools shown below (`search_outcomes`, `get_outcome_timeline`, `get_outcome_details`) are consolidated into a single `get_suggestion_outcomes(user_id, layer, query)` tool. The `layer` parameter ("search", "timeline", or "detail") controls which retrieval depth is used.

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 1: SEARCH — ~50 tokens/result                            │
│                                                                  │
│  Tool: search_outcomes(user_id, query)                          │
│                                                                  │
│  Input:                                                          │
│    user_id: "abc123"                                            │
│    query: {                                                      │
│      types: ["boost_source", "reduce_source"],                  │
│      outcomes: ["rejected"],                                     │
│      limit: 20                                                   │
│    }                                                             │
│                                                                  │
│  Output:                                                         │
│    [{                                                            │
│      id: 42,                                                     │
│      snippet: "reduce_source: theverge → rejected",             │
│      days_ago: 14,                                               │
│      score: 0.85                                                 │
│    }, ...]                                                       │
│                                                                  │
│  Agent sees: Compact list, decides which to explore             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ (only if agent needs more)
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 2: TIMELINE — ~200 tokens/result                         │
│                                                                  │
│  Tool: get_outcome_timeline(outcome_ids)                        │
│                                                                  │
│  Input: [42, 38, 25]                                            │
│                                                                  │
│  Output:                                                         │
│    [{                                                            │
│      id: 42,                                                     │
│      suggestion_type: "reduce_source",                          │
│      suggestion_value: "theverge",                              │
│      outcome: "rejected",                                        │
│      config_before: {theverge: 1.0},                            │
│      config_after: null,                                         │
│      days_ago: 14,                                               │
│      surrounding: ["accepted boost arstechnica", "..."]         │
│    }, ...]                                                       │
│                                                                  │
│  Agent sees: Context around decisions, state changes            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ (only for critical items)
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 3: DETAIL — ~500 tokens/result                           │
│                                                                  │
│  Tool: get_outcome_details(outcome_ids)                         │
│                                                                  │
│  Input: [42]                                                     │
│                                                                  │
│  Output:                                                         │
│    [{                                                            │
│      id: 42,                                                     │
│      suggestion_type: "reduce_source",                          │
│      suggestion_value: "theverge",                              │
│      outcome: "rejected",                                        │
│      user_reason: "I like their gaming coverage",               │
│      evidence_summary: {                                         │
│        like_rate: 0.35,                                          │
│        sample_size: 12,                                          │
│        negative_tags: ["too much hype"]                         │
│      },                                                          │
│      config_before: {...full config...},                        │
│      created_at: "2026-01-14T10:30:00Z",                        │
│      decided_at: "2026-01-14T10:32:00Z"                         │
│    }]                                                            │
│                                                                  │
│  Agent sees: Complete picture for deep reasoning                │
└─────────────────────────────────────────────────────────────────┘
```

### Token Savings Example

```
Scenario: Agent checking past source-related suggestions

Naive approach (fetch all):
  20 outcomes × 500 tokens = 10,000 tokens

3-Layer approach:
  Layer 1: 20 results × 50 tokens  = 1,000 tokens (search)
  Layer 2:  5 results × 200 tokens = 1,000 tokens (timeline)
  Layer 3:  1 result  × 500 tokens =   500 tokens (detail)
  Total:                             2,500 tokens

Savings: 75%
```

---

## Search Strategy

### Phase 1 (v1): Tag-Based Search

Fast, cheap, sufficient for MVP.

```sql
-- Search by type and outcome
SELECT outcome_id, suggestion_type, suggestion_value, outcome,
       julianday('now') - julianday(created_at) as days_ago
FROM suggestion_outcomes
WHERE user_id = ?
  AND suggestion_type IN (?, ?, ?)
  AND outcome IN (?, ?)
ORDER BY created_at DESC
LIMIT ?
```

### Phase 2 (v2): Hybrid Search

Combine semantic + keyword for richer matching.

```python
# Hybrid scoring (à la Clawdbot)
final_score = (0.7 * semantic_score) + (0.3 * tag_score)

# Semantic: embedding similarity
semantic_score = cosine_similarity(query_embedding, outcome_embedding)

# Tag: BM25 keyword matching
tag_score = bm25(query_tags, outcome_tags)
```

**What gets embedded:**
- Suggestion type + value
- User's reason for accept/reject
- Evidence summary

**Enables queries like:**
- "Find outcomes similar to this suggestion"
- "What happened when we suggested reducing sources?"

### Phase 3 (v3): Semantic Search with sqlite-vec

```sql
-- Add vector column for embeddings
ALTER TABLE suggestion_outcomes ADD COLUMN embedding BLOB;

-- Create virtual table for vector search
CREATE VIRTUAL TABLE outcomes_vec USING vec0(
    outcome_id INTEGER PRIMARY KEY,
    embedding FLOAT[1536]
);
```

---

## Profile Evolution

### On Each Accept/Reject

```
┌─────────────────────────────────────────────────────────────────┐
│  USER ACCEPTS/REJECTS SUGGESTION                                │
│                                                                  │
│  1. Store raw outcome                                            │
│     → INSERT INTO suggestion_outcomes (...)                      │
│                                                                  │
│  2. Update preference profile (incremental)                      │
│     → Recalculate acceptance rates by type                       │
│     → Update pattern flags                                       │
│     → Detect trend changes                                       │
│                                                                  │
│  3. Check for pattern emergence                                  │
│     → If strong pattern detected:                                │
│       Agent writes to learned-patterns.md                        │
└─────────────────────────────────────────────────────────────────┘
```

### Profile Structure

```json
{
  "user_id": "abc123",
  "computed_at": "2026-01-28T12:00:00Z",

  "acceptance_stats": {
    "add_topic": {
      "accepted": 8,
      "rejected": 2,
      "rate": 0.80,
      "confidence": "high"
    },
    "remove_topic": {
      "accepted": 1,
      "rejected": 5,
      "rate": 0.17,
      "confidence": "medium"
    },
    "boost_source": {
      "accepted": 4,
      "rejected": 3,
      "rate": 0.57,
      "confidence": "medium"
    },
    "reduce_source": {
      "accepted": 0,
      "rejected": 6,
      "rate": 0.00,
      "confidence": "high"
    }
  },

  "patterns": {
    "never_reduce_sources": true,
    "open_to_new_topics": true,
    "protective_of_existing_config": true,
    "prefers_additions_over_removals": true
  },

  "trends": {
    "engagement": "increasing",
    "preference_stability": "stable",
    "suggestion_velocity": "2.3/week"
  },

  "total_outcomes": 24,
  "last_outcome_at": "2026-01-28T10:15:00Z"
}
```

---

## Pre-Suggestion Memory Check

Before generating new suggestions, agent queries memory to avoid repeating mistakes.

```
┌─────────────────────────────────────────────────────────────────┐
│  AGENT REASONING (before suggesting)                            │
│                                                                  │
│  "I'm considering suggesting: reduce_source: theverge"          │
│                                                                  │
│  Let me check memory first...                                    │
│  → get_user_profile(user_id)                                    │
│  → sees: reduce_source acceptance rate = 0%                     │
│                                                                  │
│  → search_outcomes(user_id, {types: ["reduce_source"]})         │
│  → sees: 6 rejections, 0 acceptances                            │
│                                                                  │
│  Decision: Skip this suggestion. User never accepts source      │
│  reductions. Focus on topic additions instead.                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Compaction (Long-term Efficiency)

After accumulating many outcomes, compress old data while preserving insights.

### When to Compact

- After N outcomes (e.g., 100 per user)
- On scheduled maintenance (weekly)
- When storage exceeds threshold

### Compaction Process

```
┌─────────────────────────────────────────────────────────────────┐
│  BEFORE COMPACTION                                               │
│                                                                  │
│  suggestion_outcomes: 150 rows × ~500 tokens = 75,000 tokens    │
│  All with full context, evidence, config snapshots              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  COMPACTION STEPS                                                │
│                                                                  │
│  1. Ensure profile is fully up-to-date                          │
│  2. Archive old outcomes (keep last 30 days full)               │
│  3. For archived: keep core fields, drop large context          │
│     - Keep: id, type, value, outcome, date                      │
│     - Drop: config_before, config_after, evidence_summary       │
│  4. Update profile with "compacted_through" marker              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  AFTER COMPACTION                                                │
│                                                                  │
│  Recent outcomes (30 days): 25 rows × 500 = 12,500 tokens       │
│  Archived outcomes: 125 rows × 50 = 6,250 tokens                │
│  Profile: 1 row × 500 = 500 tokens                              │
│                                                                  │
│  Total: 19,250 tokens (74% reduction)                           │
│  All patterns preserved in profile                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tools Summary

**Note:** These are Python functions in `src/advisor_tools.py`, called via OpenAI function calling (not MCP). See [AGENT_DESIGN.md](AGENT_DESIGN.md) for the 3-layer architecture.

| Tool | Layer | Purpose | Tokens |
|------|-------|---------|--------|
| `get_user_profile` | 2 | Get computed preference profile | ~500 |
| `get_suggestion_outcomes` | 1/2/3 | 3-layer retrieval via `layer` parameter | Varies |

**get_suggestion_outcomes layers:**
- `layer="search"` → ~50 tokens/result (compact snippets)
- `layer="timeline"` → ~200 tokens/result (context around decisions)
- `layer="detail"` → ~500 tokens/result (full records)

**Outcome recording:** Handled by accept/reject API endpoints (`POST /api/suggestions/{id}/accept`), not a separate tool.

---

## Phased Implementation

### Phase 1: MVP (v1)

**Storage:**
- `suggestion_outcomes` table (full schema)
- `user_preference_profiles` table (basic)

**Retrieval:**
- Tag-based search (no embeddings)
- 3-layer retrieval pattern
- Profile lookup

**Scope:**
- Single user focus
- Manual pattern curation

### Phase 2: Hybrid Search (v2)

**Additions:**
- sqlite-vec for embeddings
- Hybrid scoring (semantic + tag)
- Automatic pattern detection

**Enables:**
- "Find similar suggestions"
- Richer context matching

### Phase 3: Full Intelligence (v3)

**Additions:**
- Compaction system
- Cross-user pattern learning (anonymized)
- Trend detection and alerts
- Auto-update learned-patterns.md

**Enables:**
- Long-term scalability
- Agent improves over time
- "Users like you tend to..."

---

## References

- [claude-mem](https://github.com/thedotmack/claude-mem) — 3-layer retrieval, token efficiency
- [OpenClaw Docs](https://docs.openclaw.ai/) — Session and context management
- [OpenClaw GitHub](https://github.com/openclaw/openclaw) — Architecture patterns
- [Clawdbot Memory](clawd.memory.md) — Two-layer storage, hybrid search, compaction
- [AGENT_DESIGN.md](AGENT_DESIGN.md) — Config advisor agent design
- [AI_CAPABILITIES.md](AI_CAPABILITIES.md) — Broader AI patterns in this project

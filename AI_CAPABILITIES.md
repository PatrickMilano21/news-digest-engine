# AI Capabilities — News Digest Engine

Engineering patterns for agents, hooks, MCPs, skills, and evals.

---

## Current Capabilities

### Agents (5 Active)

| Agent | Purpose | Trigger |
|-------|---------|---------|
| `cost-risk-reviewer` | Detects unbounded LLM calls, missing budget caps | Overnight / on-demand |
| `user-isolation-reviewer` | Finds missing `user_id` scoping in queries | Overnight / on-demand |
| `scoring-integrity-reviewer` | Validates ranking formulas, bounds checking | Overnight / on-demand |
| `test-gap-reviewer` | Detects untested code paths, missing coverage | Overnight / on-demand |
| `ux-reviewer` | Reviews customer-facing UI for issues | On-demand (after UI changes) |

**Location:** `.claude/rules/<agent-name>/`
**Output:** `artifacts/agent-findings.md`

### MCPs (Model Context Protocol Servers)

| MCP | Purpose |
|-----|---------|
| `verifier` | Run tests, fetch runs, UI smoke tests |
| `playwright` | Browser automation for UI testing |
| `browserbase` | Cloud browser (optional) |

**Config:** `.mcp.json`

### Overnight Automation

7-step workflow in `scripts/overnight_local.bat`:
1. Run 4 review agents → `agent-findings.md`
2. Summary agent verifies findings → `fix-tasks.md`
3. Codex reviews proposals → adds commentary
4. Implementation agent applies fixes → `FinalCodeFixes.md`
5. Tests run (`make test`)
6. Human reviews and approves
7. Merge to main

---

## Planned: Milestone 4.5 Additions

### ~~Skill: `suggestion-safety-check`~~ (REMOVED)

**Status:** REMOVED — validation built into `write_suggestion` MCP tool

Validation checks (now in MCP):
- Evidence count ≥ 3
- Source exists in user's feed
- Weight changes bounded ±0.3
- No duplicate pending suggestions

---

### Skill: `suggestion-eval` (Phase 2)

**Purpose:** Fixture-based regression testing for suggestion logic

**How it works:**
1. Takes a small fixture set of feedback (liked/disliked items)
2. Runs suggestion generation
3. Asserts expected suggestions are produced
4. Fails if unexpected suggestions or missing expected ones

**Usage:**
```
/suggestion-eval --fixture fixtures/config_suggestions.json
```

**Why this matters:** Regression guard when prompts or logic change. Catches drift before production.

**Status:** TODO — HIGH priority

---

### MCP: Extend Existing Verifier

**Purpose:** Add config advisor operations to existing `verifier` MCP (don't build new)

**New tools to add:**
```
mcp__verifier__run_suggest_config(user_id, date)  # Run job + validate
mcp__verifier__check_suggestion_quality(suggestion_id)  # Safety check
```

**Why extend vs new:** Reuse existing infrastructure. Verifier already handles job execution + test running.

**Status:** TODO — MEDIUM priority

---

### Post-Accept Logic (in API)

**Purpose:** Actions when user accepts a config suggestion

**Implementation:** Python code in `POST /api/suggestions/{id}/accept` handler

**Actions:**
1. Backup previous config (store in `suggestion_outcomes.config_before`)
2. Apply change to `user_configs`
3. Log outcome with rich snapshot
4. Update `user_preference_profiles`

**Status:** Designed in AGENT_DESIGN.md — ready to implement

---

### Pre-Digest Nudge (Future)

**Purpose:** Nudge user about pending suggestions before digest

**Implementation:** Python code in digest rendering

**Actions:**
- Check if user has pending suggestions
- Add banner to digest: "You have 3 config suggestions waiting"
- No auto-apply — awareness only

**Status:** FUTURE — nice nudge, not critical for v1

---

### Agent: `config-advisor-reviewer` (Optional)

**Purpose:** Deeper review of generated suggestions (beyond inline safety check)

**When to use:**
- Part of overnight workflow for batch review
- When safety-check passes but want human-level judgment
- For auditing suggestion quality over time

**Checks:**
- Evidence quality (not cherry-picked, representative sample)
- Suggestion reasoning makes sense
- No subtle hallucinations safety-check might miss

**Output:** `artifacts/suggestion-review.md`

**Status:** TODO — LOW priority (safety-check skill handles critical path)

---

## Agent Memory Patterns

*Inspired by [claude-mem](https://github.com/thedotmack/claude-mem) architecture*

### 3-Layer Retrieval Pattern

Token-efficient memory access (10x savings vs fetching everything):

| Layer | Purpose | Tokens | Returns |
|-------|---------|--------|---------|
| **Search** | Find relevant outcomes | ~50/result | `{id, snippet, tags}` |
| **Timeline** | Context around results | ~200/result | `{id, before, after, date}` |
| **Detail** | Full records when needed | ~500/result | Complete outcome record |

**Implementation:**
```python
# Layer 1: Search (lightweight)
def search_outcomes(user_id, query_tags) -> list[{id, snippet}]

# Layer 2: Timeline (context)
def get_outcome_timeline(user_id, outcome_ids) -> list[{id, before, after}]

# Layer 3: Detail (full data)
def get_outcome_details(outcome_ids) -> list[full_record]
```

### v1 Memory (Adopt Easy Patterns)

| Pattern | Implementation | Difficulty |
|---------|----------------|------------|
| **Hooks-based capture** | Hook on accept/reject API calls | EASY |
| **SQLite storage** | `suggestion_outcomes` table | EASY |
| **3-layer retrieval** | Agent tools for search/timeline/detail | MEDIUM |
| **Tag-based search** | Query by suggestion_type, user_id, outcome | EASY |

### v2 Memory (Add If Needed)

| Pattern | Implementation | Difficulty |
|---------|----------------|------------|
| **Semantic search** | Embeddings + vector similarity | HARD |
| **Cross-user patterns** | "Users who like X tend to reject Y" | MEDIUM |
| **Prompt adaptation** | Auto-adjust prompts based on outcomes | MEDIUM |

### Outcome Storage Schema

```sql
CREATE TABLE suggestion_outcomes (
    outcome_id INTEGER PRIMARY KEY,
    suggestion_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    suggestion_type TEXT NOT NULL,
    outcome TEXT NOT NULL,  -- 'accepted', 'rejected', 'expired'
    context_snapshot TEXT,  -- JSON: config state at decision time
    created_at TEXT NOT NULL,
    FOREIGN KEY (suggestion_id) REFERENCES config_suggestions(suggestion_id)
);

-- Index for 3-layer retrieval
CREATE INDEX idx_outcomes_user_type ON suggestion_outcomes(user_id, suggestion_type);
CREATE INDEX idx_outcomes_date ON suggestion_outcomes(created_at);
```

---

## Future Considerations

### Learning Loop for Config Advisor

**Concept:** Track which suggestions get accepted/rejected, feed patterns back into prompt

**How:**
1. Capture outcomes via `post-accept-hook` / `post-reject-hook`
2. Store in `suggestion_outcomes` table
3. Agent queries: "What has this user rejected before?"
4. Use 3-layer retrieval for token efficiency
5. Adapt prompt: "Users rarely accept source weight reductions"

**Status:** FUTURE (need acceptance data first)

---

## Priority Matrix (Updated)

| Capability | Priority | Status |
|------------|----------|--------|
| Extend Verifier MCP (5 tools) | **HIGH** | Designed — ready to implement |
| Agent file + prompt | **HIGH** | Designed — ready to implement |
| API endpoints (4 routes) | **HIGH** | Designed — ready to implement |
| DB schema (3 tables) | **HIGH** | Designed — ready to implement |
| `suggestion-eval` skill | MEDIUM | Phase 2 |
| Pre-digest nudge | LOW | Future |
| `config-advisor-reviewer` agent | LOW | Future (safety built into MCP) |

---

## Agent Directory Structure

*From [Anthropic docs](https://code.claude.com/docs/en/sub-agents)*

### Recommended Layout

```
.claude/
├── agents/
│   └── config-advisor.md       # Agent definition (YAML frontmatter + prompt)
├── rules/
│   └── config-advisor/         # Learned patterns (like review agents)
│       ├── learned-patterns.md
│       └── run-history.md
└── CLAUDE.md
```

### Agent File Format

```markdown
---
name: config-advisor
description: Senior engineer that analyzes user feedback and suggests config improvements. Use proactively when generating config suggestions.
tools: Read, Grep, Glob, Bash
model: sonnet
---

You are a senior engineer helping optimize this user's news digest...

[Full persona and reasoning framework here]
```

### Scope Options

| Location | Scope | Use Case |
|----------|-------|----------|
| `.claude/agents/` | Project | Team-shared, version controlled |
| `~/.claude/agents/` | User | Personal, all projects |
| `--agents` CLI flag | Session | Testing, automation |

---

## References

- **Agent rules:** `.claude/rules/`
- **Agent definitions:** `.claude/agents/`
- **MCP config:** `.mcp.json`
- **Overnight script:** `scripts/overnight_local.bat`
- **Status:** `STATUS.md`
- **Agent design:** `AGENT_DESIGN.md`
- **Claude-mem patterns:** https://github.com/thedotmack/claude-mem

# Overnight Run Planning

Automated overnight job that runs all review agents, produces artifacts, and prepares reviews for human approval.

---

## Goals

1. Run all 5 review agents overnight (unattended)
2. Produce consolidated findings artifact
3. Keep changes isolated in a branch until human approves
4. Have Codex + Claude reviews ready for morning
5. Never auto-merge or overwrite main code

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OVERNIGHT ORCHESTRATOR                    │
│                    (jobs/overnight_run.py)                   │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ Phase 1:      │   │ Phase 2:      │   │ Phase 3:      │
│ Code Analysis │   │ UX Review     │   │ Summary       │
│ (4 agents)    │   │ (1 agent)     │   │ & Notify      │
└───────────────┘   └───────────────┘   └───────────────┘
        │                   │                   │
        ▼                   ▼                   ▼
   No server needed    Server lifecycle    Consolidate
   Run in parallel     Start → Run → Stop  artifacts
```

---

## Branch Strategy

**Rule: Never run on main. Never auto-merge.**

```
main (protected)
  │
  └── overnight/review-{date}  ← Created fresh each night
        │
        ├── Agent findings written here
        ├── Learning files updated here
        └── Ready for human review in morning
```

**Workflow:**
1. Orchestrator creates branch `overnight/review-YYYY-MM-DD`
2. Agents run and write to that branch
3. Human reviews findings in morning
4. Human merges or discards branch

---

## Phase 1: Code Analysis Agents

**Agents:** user-isolation, test-gap, scoring-integrity, cost-risk

| Check | Description |
|-------|-------------|
| Pre-check | Ensure `make test` passes before running |
| Run | Invoke all 4 agents (can be parallel - no dependencies) |
| Post-check | Verify each agent wrote to agent-findings.md |
| Failure handling | Log error, continue to next agent |

**No server needed.** These scan files only.

---

## Phase 2: UX Review Agent

**Agent:** ux-reviewer

| Check | Description |
|-------|-------------|
| Pre-check | Port 8001 not already in use |
| Start server | `uvicorn src.main:app --port 8001` |
| Health check | Wait for `GET /health` to return 200 |
| Run | Invoke ux-reviewer with URL + scenario |
| Post-check | Verify agent wrote to agent-findings.md |
| Stop server | `server.terminate()` in finally block |
| Cleanup | Ensure port 8001 released |

**Server lifecycle:**
```python
server = None
try:
    server = subprocess.Popen([...uvicorn...])
    wait_for_health("http://localhost:8001/health", timeout=10)
    run_ux_reviewer(url, scenario)
finally:
    if server:
        server.terminate()
        server.wait(timeout=5)
```

**Pages to review:**
| Page | URL | Scenario |
|------|-----|----------|
| Date digest | `/ui/date/{latest_date}` | Non-technical user reading news |
| Item detail | `/ui/item/{sample_id}` | User clicking through from digest |
| History | `/ui/history` | Returning user checking past digests |

---

## Phase 3: Summary & Notification

After all agents complete:

1. **Consolidate findings**
   - Count critical/medium/low issues per agent
   - Generate summary at top of agent-findings.md

2. **Generate review checklist**
   ```markdown
   ## Overnight Review - 2026-01-30

   Branch: overnight/review-2026-01-30

   ### Summary
   - Critical issues: 3
   - Medium issues: 5
   - Low issues: 8

   ### Agent Status
   - [x] user-isolation-reviewer: 5 issues
   - [x] test-gap-reviewer: 13 issues
   - [x] scoring-integrity-reviewer: 3 issues
   - [x] cost-risk-reviewer: 2 issues
   - [x] ux-reviewer: 11 issues

   ### Action Required
   Review findings in artifacts/agent-findings.md
   Then: merge branch or discard
   ```

3. **Notify** (optional)
   - Email summary to Patrick
   - Or: Write to a known file location human checks

---

## Open Questions (Need Decisions)

### 1. How to invoke agents programmatically?

**Options:**
- A) Claude Code CLI: `claude --agent user-isolation-reviewer`
- B) Direct prompt via API (requires API key + setup)
- C) Script that simulates user asking Claude to run agent

**Recommendation:** Research Claude Code CLI options first.

### 2. Run time?

**Options:**
- A) 2 AM local time (after dev activity)
- B) On git push to specific branch
- C) Manual trigger with automation ready

**Recommendation:** Start with manual trigger (C), automate later.

### 3. What triggers a run?

**Options:**
- A) Cron/scheduled task
- B) Git hook (post-push)
- C) Manual: `python jobs/overnight_run.py`

**Recommendation:** Start manual (C), add cron later.

### 4. Codex vs Claude reviews?

**Clarification needed:**
- Should Codex (Anthropic's tool) review the findings?
- Should Claude (in this session) summarize findings?
- Or both produce separate outputs?

---

## Implementation Plan

### Step 1: Research
- [ ] How to invoke Claude Code agents from Python/CLI
- [ ] Test with one agent manually

### Step 2: Orchestrator Script
- [ ] Create `jobs/overnight_run.py`
- [ ] Implement branch creation
- [ ] Implement Phase 1 (code agents)
- [ ] Implement Phase 2 (UX + server lifecycle)
- [ ] Implement Phase 3 (summary)

### Step 3: Testing
- [ ] Run manually, verify artifacts created
- [ ] Verify branch isolation works
- [ ] Verify server cleanup works

### Step 4: Automation (Later)
- [ ] Add cron/scheduled task
- [ ] Add notification (email/slack)

---

## Guards & Safety

| Guard | Purpose |
|-------|---------|
| Branch isolation | Never write to main |
| Test gate | `make test` must pass before agents run |
| Server cleanup | Always terminate in finally block |
| Timeout | Each agent has max runtime (5 min?) |
| Failure isolation | One agent failing doesn't stop others |
| No auto-merge | Human always reviews and merges |

---

## Files Created/Modified by Overnight Run

| File | Action |
|------|--------|
| `artifacts/agent-findings.md` | Replaced (each agent's section) |
| `.claude/rules/{agent}/learned-patterns.md` | Updated |
| `.claude/rules/{agent}/run-history.md` | Appended |
| `artifacts/overnight-summary-{date}.md` | Created (new) |

---

## Next Step

**Decision needed:** How do we invoke agents programmatically?

Once we know that, we can build the orchestrator.

# CLAUDE.md

Execution rules for Claude Code. Read this first. Do not rely on chat memory.

**Plan:** `week4.md` (Codex maintains)
**Progress:** `STATUS.md` (Claude maintains)

---

## Execution Mode

Claude Code is a **primary implementer** on feature branches (`agent/<task>`), never on `main`.

Claude is allowed to:
- Edit files on the current branch
- Refactor within scope
- Write and run tests

Claude must NEVER:
- Write to `main` branch
- Run `git commit`, `git merge`, or `git push`
- Change schemas, eval logic, or grounding semantics
- Bypass tests

Patrick owns all git commands and merges.

---

## Task Tracking (REQUIRED)

Use `TaskCreate` to break work into visible steps:
1. Create tasks for each major step
2. Mark `in_progress` when starting
3. Mark `completed` when done
4. Use `TaskList` to show current state

---

## Subagent Policy

### UX Reviewer
- **When:** New customer-facing page or material UI layout change
- **Invoke:** Once per surface, after layout stabilizes, before human review
- **Input:** Exact URL or HTML snapshot + short context
- **Output:** 5-10 bullets (issue, why, fix) + 2-3 low-risk improvements
- **Forbidden:** Code edits, schema changes, debug surfaces, scope expansion

---

## Acceptance Checklist (Pre-Merge)

Patrick confirms before any merge:
- [ ] Tests green (`make test`)
- [ ] UI manually clicked (happy path + refusal)
- [ ] No debug data leaked to customer UI
- [ ] Diff reviewed
- [ ] Change explainable in 2 sentences

---

## Common Commands

```powershell
make test                    # Run all tests
make dev                     # Start dev server (port 8001)
make run DATE=2026-01-15     # Run daily job
make eval DATE=2026-01-15    # Run evaluation harness
/agents                      # Reload agents after file changes
```

---

## Reference Docs

**Claude Code:**
- Subagents: https://docs.anthropic.com/en/docs/claude-code/sub-agents
- Hooks: https://docs.anthropic.com/en/docs/claude-code/hooks
- Memory/Rules: https://docs.anthropic.com/en/docs/claude-code/memory
- MCP: https://docs.anthropic.com/en/docs/claude-code/mcp

**Anthropic:**
- Evals Guide: https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents

**MCPs in this project (`.mcp.json`):**
- `verifier` — Run tests, fetch runs, UI smoke tests
- `playwright` — Browser automation (used by ux-reviewer)
- `browserbase` — Cloud browser (optional)

# CLAUDE.md

Execution rules for Claude Code. Read this first. Do not rely on chat memory.

**Plan:** `week4.md` (Codex maintains)
**Progress:** `STATUS.md` (Claude maintains)

---

## Execution Mode

Claude Code is a **primary implementer** on feature branches (`agent/<task>`).

**Branch workflow:**
- Work on `agent/milestone1` (or similar feature branch)
- When task complete → Patrick merges to `main`
- Sync branches (`git merge main`) before next task

Claude is allowed to:
- Edit files on the current branch
- Refactor within scope
- Write and run tests

Claude must NEVER:
- Push directly to `main` branch
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

**After each completed task:**
- Update `STATUS.md` (mark step done, update DoD checkboxes)
- Update `completion.md` (dated entry with files changed + verification)
- Review `CLAUDE.md` for any new patterns or corrections

**Test running policy:**
- Do NOT run `make test` after every implementation step
- Patrick assigns test runs separately (or to another agent)
- Only run tests when explicitly asked or at the end of a full implementation sequence

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

**Project Design Docs:**
- Config Advisor Agent: `AGENT_DESIGN.md`
- Memory Architecture: `MEMORY_DESIGN.md`
- AI Capabilities: `AI_CAPABILITIES.md`

---

## AI Workflow Best Practices

*Source: Claude Code team (Boris et al.) — applies to agents, automation, and AI-assisted development*

### Self-Improvement (Claude's Ongoing Job)

**This is critical:** When you discover a high-level rule, pattern, or learn from a correction — **update this file immediately.**

- After any correction: "Update CLAUDE.md so you don't make that mistake again"
- Claude is good at writing rules for itself — do it proactively
- Convert repeated mistakes into: a test, a hook, a skill, or a rule here
- Review `.claude/rules/*/learned-patterns.md` for agent-specific patterns

**This file should grow over time as patterns emerge.**

### Planning

- **Plan mode first** for complex tasks (3+ steps, cross-file, architectural)
- Pour energy into the plan so implementation can be 1-shot
- If something goes sideways: STOP and re-plan — don't keep pushing
- For risky changes: use a second Claude/Codex to review the plan

### Subagents & Parallelization

- Use subagents to keep main context window clean
- Offload: research, exploration, log analysis, parallel tasks
- For complex problems: "use subagents" to throw more compute at it
- One task per subagent — focused execution, structured output

### When NOT to Use Subagents

Subagents add latency. Skip them when:
- Quick, targeted changes (< 3 files)
- Context is already loaded in main conversation
- Latency matters (user waiting)
- Sequential dependent steps — chain in main context instead

### Cost Awareness

- Use **Haiku** for exploration, research, and read-only subagents
- Use **Sonnet** for implementation and complex reasoning
- Use **Opus** only when explicitly needed (deep analysis, critical decisions)
- Track token usage on complex multi-step tasks

### MCP Tool Development

- Extend existing MCPs (`verifier`) rather than creating new servers
- Custom tools can also be Bash scripts the agent calls
- Test tools independently before agent integration
- Agent accesses MCP tools via `mcp__<server>__<tool>` pattern

### Skills & Reuse

- If you do something more than once a day, make it a skill
- Commit skills to git — reuse across projects
- Check `.claude/agents/` for existing skills before building new

### Verification

- Never mark done without proving it works
- "Grill me on these changes", "Prove to me this works"
- Diff behavior between main and your branch when relevant
- Demonstrate correctness: tests, logs, artifacts

### Prompting Patterns

- Challenge Claude: "Don't make a PR until I pass your test"
- After a mediocre fix: "Knowing everything you know now, implement the elegant solution"
- Reduce ambiguity: detailed specs before handing off work

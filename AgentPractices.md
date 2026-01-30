# Agent Best Practices

What we've learned about building Claude Code subagents. Mix of official Anthropic patterns and our own design decisions.

---

## The Core Question

> **"What actions must this agent take to complete its task?"**

Answer this first. Then map actions to tools.

---

## Tool Selection Decision Tree

| Need | Tool(s) |
|------|---------|
| Read source code/files | `Read, Glob` |
| Search for patterns in code | `Grep` |
| Find files by name/pattern | `Glob` |
| Write findings/update files | `Write` |
| See rendered UI (visual) | `Playwright MCP` |
| Run commands/tests | `Bash` |
| Fetch external docs/sites | `WebFetch, WebSearch` |

**Principle of least privilege:** Only give tools the agent needs. More tools = more risk.

### Agent Type → Tool Mapping

| Agent Type | Job | Typical Tools |
|------------|-----|---------------|
| Code analysis | Read code, find patterns | `Read, Grep, Glob, Write` |
| UI/visual review | Render and inspect UI | `Playwright MCP, Read, Write` |
| Test runner | Execute tests | `Bash, Read, Write` |
| External research | Look up docs/APIs | `WebFetch, WebSearch, Read` |

---

## File Structure (Official Pattern)

```
.claude/
├── agents/                    # Agent definitions
│   └── {agent-name}.md        # YAML frontmatter + prompt
└── rules/                     # Agent memory (our custom addition)
    └── {agent-name}/
        ├── learned-patterns.md   # Self-updating patterns
        ├── human-overrides.md    # Human corrections (always wins)
        └── run-history.md        # Audit log
```

Central findings file:
```
artifacts/
└── agent-findings.md          # All agents report here, each replaces own section
```

---

## Agent File Format (Official)

```markdown
---
name: agent-name
description: "When to use this agent. Keep concise."
tools: Read, Grep, Glob, Write
model: sonnet
color: blue
---

You are a [Role] ensuring [Goal].

When invoked:
1. Read human-overrides.md — these ALWAYS take precedence
2. Scan the codebase for [issues]
3. Replace your section in agent-findings.md
4. Update learned-patterns.md — keep under 50 lines
5. Update run-history.md — keep last 10 runs

Write restriction: Only write to [specific files]. Never modify code or config.

[Domain-specific checks]

[Output format]
```

**Target length:** 30-50 lines. Focused, not exhaustive.

---

## Self-Learning Architecture (Custom Design)

### The Loop

```
┌─────────────────────────────────────────────────────┐
│  Agent runs → reads learned-patterns.md             │
│      ↓                                              │
│  Scans codebase with that context                   │
│      ↓                                              │
│  Updates findings + learns new patterns             │
│      ↓                                              │
│  Human reviews → adds overrides if needed           │
│      ↓                                              │
│  Next run benefits from both                        │
└─────────────────────────────────────────────────────┘
```

### File Purposes

| File | Who Writes | Purpose | Size Limit |
|------|------------|---------|------------|
| `learned-patterns.md` | Agent | Safe/risky patterns discovered | 50 lines max |
| `human-overrides.md` | Human only | Corrections that always win | No limit |
| `run-history.md` | Agent | Audit log of runs | Last 10 runs |
| `agent-findings.md` | Agent | Current findings (replaced each run) | Per-section |

### Why This Works

- **Agent improves over time** — learns what to flag/ignore
- **Human stays in control** — overrides always take precedence
- **Auditable** — run history shows what was checked
- **Bounded growth** — size limits prevent context bloat

---

## Section Markers in Findings File

Each agent gets a section with HTML comment markers:

```markdown
<!-- AGENT-NAME:START -->
## Agent Name Review

[Findings here]

<!-- AGENT-NAME:END -->
```

Agent replaces content between its markers. Other agents' sections stay intact.

---

## Testing an Agent

1. **Run once** — verify it scans and updates all files
2. **Run twice** — verify self-learning:
   - `agent-findings.md` — section replaced (not appended)
   - `learned-patterns.md` — statistics updated, patterns refined
   - `run-history.md` — new entry appended
   - `human-overrides.md` — unchanged (agent never writes here)

If run #2 finds different issues than run #1, that's the agent learning/improving.

---

## What's Official vs. Custom

| Pattern | Source |
|---------|--------|
| `.claude/agents/*.md` location | Official docs |
| YAML frontmatter (name, tools, model) | Official docs |
| `.claude/rules/` for memory | Custom (our design) |
| Self-learning loop | Custom (our design) |
| Size constraints (50 lines, 10 runs) | Custom (our design) |
| Central findings file with section markers | Custom (our design) |
| Human overrides always win | Custom (our design) |

---

## Checklist for New Agents

- [ ] Define the core question: "What actions must this agent take?"
- [ ] Select minimum necessary tools
- [ ] Create agent file in `.claude/agents/`
- [ ] Create rules directory with 3 files (learned-patterns, human-overrides, run-history)
- [ ] Add section markers to `artifacts/agent-findings.md`
- [ ] Write focused prompt (30-50 lines)
- [ ] Include write restrictions
- [ ] Include size constraints in instructions
- [ ] Test run #1 — verify file updates
- [ ] Test run #2 — verify self-learning behavior

---

## Common Mistakes

1. **Too many tools** — gives agent capabilities it doesn't need
2. **No write restrictions** — agent might modify code/config
3. **No size limits** — files grow unbounded
4. **Vague definitions** — "public function" should be explicit
5. **Missing section markers** — agents overwrite each other's findings
6. **Forgetting human-overrides** — no way to correct false positives

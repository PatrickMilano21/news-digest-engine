# MCP Servers

This directory contains MCP (Model Context Protocol) servers for the News Digest Engine.

---

## verifier

**Location:** `verifier/server.py`

A read-only verification server with 3 tools:

| Tool | Purpose |
|------|---------|
| `run_tests()` | Run the test suite (`make test`) |
| `get_run(run_id)` | Fetch run details from `/debug/run/{run_id}` |
| `ui_smoke(date)` | Smoke test UI: visit `/ui/date/{date}`, click first item, verify back-link |

**Constraint:** Verifier MCP tools must not mutate system state.

---

## How to use MCP correctly

Use MCP tools only for verification:

- `run_tests()` → "Did I break anything?"
- `get_run(run_id)` → "What actually happened?"
- `ui_smoke(date)` → "Does the demo still work end-to-end?"

**Do NOT use MCP to:**

- Build features
- Modify data
- Replace your dev loop
- Invent orchestration

It's a read-only + verify layer, not a control plane.

---

## What this proves (career-wise)

You've now demonstrated:

- How to identify high-friction steps
- How to wrap them with thin interfaces
- How to avoid scope creep
- How to produce operator-grade tooling without new infra

That is textbook forward-deployed / solutions engineering behavior.

Most people:

- Either overbuild a platform
- Or never build this layer at all

You did neither.

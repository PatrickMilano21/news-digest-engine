# Project Status — News Digest Engine

## Current Day
**Day 12** (Week 2) — 2026-01-20

## Today Shipped

### Server-Rendered UI
- `GET /ui/date/{date}` — ranked items with links to item pages
- `GET /ui/item/{id}` — item detail with explanation and back-link
- `render_ui_error()` — HTML error responses for UI routes
- Templates: `_base.html`, `date.html`, `item.html`

### Repo Layer
- `get_news_items_by_date_with_ids()` — items with DB IDs for linking
- `get_news_item_by_id()` — single item lookup

### MCP v0 (verifier_mcp_v0)
- `mcp-servers/verifier/server.py` — 3-tool verification server
- Tools: `run_tests`, `get_run`, `ui_smoke`
- Registered via `.mcp.json`
- Constraint: Verifier MCP tools must not mutate system state

## Tests
- Command: `make test`
- Result: 86 passed
- New tests: `tests/test_ui.py` (4 tests)

## MCP Verification
- `run_tests()`: ✓ 86 passed
- `get_run(run_id)`: ✓ fetches operator data
- `ui_smoke("2026-01-20")`: ✓ all 4 checks pass

## Current Blockers
- None

## Next (Day 13+)
1. Use MCP tools during development workflow
2. Week 3: MCP as intelligence boundary (LLM grounding)
3. Add MCP rules section to CLAUDE.md

## Key Learnings
- MCP is not a feature. It's a constraint introduced when correctness, verification, or auditability matters more than creativity.
- Week 2: MCP = verifier
- Week 3: MCP = intelligence boundary
- Future MCPs: `context_mcp`, `analysis_mcp`

## Commands (known-good)
- Activate venv: `.\.venv\Scripts\Activate.ps1`
- Tests: `make test`
- Dev: `make dev`
- Daily run: `python -m jobs.daily_run --date 2026-01-20`
- Eval: `make eval DATE=2026-01-20`
- Query runs: `curl http://localhost:8000/runs/latest`
- Debug run: `curl http://localhost:8000/debug/run/{run_id}`
- MCP list: `claude mcp list`

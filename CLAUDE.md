# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Always read this file first. Do not rely on chat memory.**

## Execution Mode (AUTHORITATIVE)

This repository is now in **execution mode**, not training mode.

Claude Code is treated as a **primary implementer** operating on
**feature branches** (`agent/<task>`), not on `main`.

The workflow is:

1. A short written plan is produced (PLAN v1) and saved to `STATUS.md`.
2. Claude executes the plan on a branch.
3. Tests + evals enforce correctness.
4. Patrick reviews diffs, UI, and behavior.
5. Changes are merged to `main` only when approved.

Claude is allowed to:
- edit multiple files
- refactor code within scope
- write tests
- run tests

### Task Tracking (REQUIRED)

Always use `TaskCreate` at the start of executing a plan to break down the work into visible steps. This provides:
- Progress visibility for Patrick
- Clear checkpoints for review
- Resume capability if session is interrupted

When starting a ticket:
1. Create tasks for each major step in the plan
2. Mark tasks `in_progress` when starting work
3. Mark tasks `completed` when done
4. Use `TaskList` to show current state

Claude is NOT allowed to:
- change schemas
- weaken grounding or refusal semantics
- change eval logic or thresholds
- bypass tests
- commit or merge code

## Project Overview

News Digest Engine is a FastAPI service that ingests RSS feeds, normalizes/deduplicates items, ranks them deterministically, and produces HTML digests with explainability.

**Goal:** Demonstrate FDE / Applied / Solutions engineering by shipping a deterministic, test-driven backend:

```
Ingest → normalize/dedupe → rank → artifacts → run history → evals → (later) LLM grounding + citations
```

**Primary repo:** `news-digest-engine`
**Gym repo:** `fde-drills`

### Non-negotiables
- Deterministic + test-driven
- Debuggable + boring competence
- No scope creep while tests are red
- Strict build protocol

## Reference Documents (`docs/raw/` - READ ONLY)

| File | Purpose | Authority |
|------|---------|-----------|
| `AI Job Pivot Handoff_ Source of Truth.docx` | Build protocol / how we work | AUTHORITATIVE — wins on process |
| `Locked_Syllabus.docx` | Day-by-day tasks, DoD, required artifacts | AUTHORITATIVE — no invented scope |
| `Locked_Portfolio_v1.docx` | Role targeting (OpenAI FDE), tradeoff justification | AUTHORITATIVE |
| `LinkedIN Profile.docx` | External narrative, recruiter language | REFERENCE only |

## Operating Rules (for assistants)

- Treat `docs/raw/` as read-only (do not edit .docx files).
- Start work by reading `CLAUDE.md` and then checking `docs/raw/Locked_Syllabus.docx` for the next incomplete day.
- When coding, follow: **PLAN v1 → Claude execution → human review**
- No code changes are allowed unless a PLAN v1 exists in `STATUS.md`.

**PLAN v1 format (written to STATUS.md before implementation):**
```
## Current Plan

PLAN v1: <ticket-name>
Objective:
Steps:
Files to touch:
Tests to add/update:
Done when:
```

Plans live in STATUS.md so they persist across sessions and can be reviewed in diffs.
- Keep tests green. If red: fix the smallest failing thing only.
- End each step with: what changed, commands to run, and what "green" looks like.
- When a module name changes, update the Architecture section in the same commit.

## Code suggestions vs file edits (IMPORTANT)

Default behavior:
- You MAY provide code snippets in the chat (reference snippets / minimal diffs).
- You MUST NOT write or modify code files in the repo unless explicitly unlocked.

File edit unlock phrases:
- **FILE_EDIT_MODE: ON** (you may edit code files)
- **FILE_EDIT_MODE: OFF** (return to chat-only suggestions)
- **EDIT_ONLY: <path>** (permission to edit exactly one file)

Even when giving code snippets:
- Follow English spec → YOUR MOVE → reference
- Do not dump full solutions upfront
- Provide only the mini-step snippet, not multi-step combined code

Current mode (default): **FILE_EDIT_MODE: ON (branch-only)**

Claude may edit files **only on non-main branches**.
Claude must stop immediately if tests fail.

## Branch Discipline (NON-NEGOTIABLE)

Claude must never write directly to `main`.

All work happens on branches named:
- `agent/<ticket-name>`

Claude may assume the current working directory reflects
the active branch.

Patrick is responsible for:
- reviewing diffs (`git diff main...HEAD`)
- running final tests
- merging to `main`

Claude must never run:
- `git commit`
- `git merge`
- `git push`

### Branch Workflow (human-executed)

```powershell
# Before Claude starts a ticket:
git checkout main
git pull
git checkout -b agent/<ticket-name>

# After tests pass + acceptance checklist:
git diff main...HEAD          # Review all changes
git checkout main
git merge agent/<ticket-name>
git branch -d agent/<ticket-name>  # Clean up
```

Claude works only on the active branch. Patrick owns all git commands.

## End-of-day workflow (git + status)

At the end of a day:
1) Update `STATUS.md` with:
   - Day number + date
   - Shipped features (bullets)
   - Tests added/updated (count)
   - Remaining blockers
   - Next day target
2) Prepare a commit plan:
   - Show `git status` summary
   - Propose the exact `git add` paths (never `git add -A`)
   - Propose a commit message: `dayXX: <tight summary>`
3) DO NOT run `git commit` automatically.
   - I (Patrick) will run the final commands.
4) Never stage/commit:
   - `.claude/`, `.env`, `data/`, secrets, large artifacts
5) **Claude must never run git commands.** All git is executed manually in a separate terminal.

## Trigger: END_OF_DAY DayXX

When I say: **END_OF_DAY DayXX**

Do not modify code files. Only update `STATUS.md` and output git commands.

Claude must:
1) Create/update `STATUS.md` (repo root) with:
   - Current Day (DayXX + date)
   - Today Shipped
   - Tests (command + pass/fail)
   - Current Blockers
   - Next (top 3)
   - Commands (known-good)
2) Print sanity checks (yes/no):
   - STATUS.md updated today
   - Exactly one commit planned (unless hotfix)
   - Commit message starts with `dayXX:`
   - Tests green right now (if unknown, say NO and show command)
3) Output git plan as commands only (do not execute):
   - `git status`
   - `git diff`
   - `git add <explicit paths>` (never `git add -A`)
   - `git commit -m "dayXX: <tight summary>"`

Constraints:
- Never stage/commit: `.claude/`, `.env*`, `data/`, secrets, large artifacts.
- If tests are red/unknown, stop at git plan and tell me the smallest next step to get green.

## Trigger: DOCS_ONLY

When I say: **DOCS_ONLY**
- You may edit only: `CLAUDE.md`, `STATUS.md`, and markdown files under `docs/` or `writeups/`.
- Do not modify any code files.

## Common Commands

```powershell
# Run tests
make test

# Run single test
.\.venv\Scripts\python.exe -m pytest tests/test_scoring.py -q

# Start dev server (port 8000 with reload)
make dev

# Run daily job for a specific date
make run DATE=2025-01-15

# Run evaluation harness
make eval DATE=2025-01-15
```

## Architecture

### Data Flow
```
RSS XML → rss_fetch.py → rss_parse.py → normalize.py → repo.py (SQLite)
                                              ↓
                        scoring.py ← get_news_items_by_date()
                              ↓
                        explain.py → artifacts.py → HTML digest
```

### Key Modules

- **`src/main.py`**: FastAPI routes only — thin handlers that delegate to other modules
- **`src/views.py`**: Display/presentation logic — builds view models for templates (changes often with UI)
- **`src/schemas.py`**: `NewsItem` model + normalization functions (`normalize_url`, `normalize_title`, `dedupe_key`)
- **`src/scoring.py`**: `RankConfig` model + `rank_items()` - deterministic ranking by score → timestamp → index
- **`src/repo.py`**: SQLite CRUD for `news_items` and `runs` tables
- **`src/explain.py`**: Score explanations — why an item ranked where it did
- **`jobs/daily_run.py`**: CLI for daily batch job with idempotency (skips if run exists for day)
- **`jobs/build_digest.py`**: Generates HTML digest artifacts

### Database

SQLite at `data/news.db` (overridden via `NEWS_DB_PATH` env var in tests).

**Tables:**
- `news_items`: `dedupe_key` (UNIQUE), source, url, published_at, title, evidence
- `runs`: run_id (PK), started_at, finished_at, status, metrics, error fields

### Repo Layer (`src/repo.py`)

All database access goes through these functions:

**news_items:**
- `insert_news_items(conn, items)` → `{inserted, duplicates}` - bulk insert with INSERT OR IGNORE
- `get_news_items_by_date(conn, day=)` → `list[NewsItem]` - fetch items for a YYYY-MM-DD day

**runs:**
- `start_run(conn, run_id, started_at, received)` - create new run record
- `finish_run_ok(conn, run_id, finished_at, *, after_dedupe, inserted, duplicates)` - mark success
- `finish_run_error(conn, run_id, finished_at, *, error_type, error_message)` - mark failure
- `get_latest_run(conn)` → `dict | None` - most recent run
- `get_run_by_day(conn, day=)` → `dict | None` - most recent run for a day
- `get_run_by_id(conn, run_id=)` → `dict | None` - lookup by ID
- `has_successful_run_for_day(conn, day=)` → `bool` - idempotency check
- `report_runs_by_day(conn, limit=7)` → `list[dict]` - aggregated daily stats

### Deduplication

SHA256 of `normalized_url|normalized_title` produces stable `dedupe_key`. Python-level dedupe happens first, then DB-level via UNIQUE constraint.

### Ranking Algorithm

```python
score = (1.0 + relevance) × source_weight × recency_decay
# where relevance = topic_matches + keyword_boosts
```

Base score of 1.0 ensures recency always contributes. Default topics include: AI, startup, funding, cloud, security, open source.

Ties broken by: score desc → published_at desc → original index asc

## Code Organization Patterns

**IMPORTANT**: Follow these patterns to keep the codebase maintainable.

### Directory Structure

```
src/
├── main.py          # FastAPI routes ONLY (no HTML, minimal logic)
├── views.py         # Display/presentation logic (view models for templates)
├── repo.py          # ALL database access (SQLite CRUD)
├── db.py            # Database connection + schema init
├── schemas.py       # Pydantic models + validation
├── scoring.py       # Ranking algorithm
├── explain.py       # Score explanations
├── artifacts.py     # Static file generation (digest HTML saved to disk)
├── clients/         # External API clients (LLM, etc.)
└── llm_schemas/     # LLM-specific schemas

templates/           # Jinja2 templates for web UI
├── _base.html       # Base layout (inherited by all pages)
├── home.html        # Home page
├── date.html        # Date digest page
└── item.html        # Item detail page

jobs/                # CLI batch jobs
├── daily_run.py     # Daily pipeline
└── build_digest.py  # Digest artifact builder

tests/               # All tests (mirror src/ structure)
evals/               # Evaluation cases and runner
```

### Where Code Belongs

| Type of Code | Location | Notes |
|--------------|----------|-------|
| **API routes** | `src/main.py` | Route definitions only. Call other modules for logic. |
| **Display/view logic** | `src/views.py` | Builds view models for templates. Changes often with UI. |
| **HTML for web UI** | `templates/*.html` | Jinja2 templates. NEVER inline HTML in Python. |
| **HTML for artifacts** | `src/artifacts.py` | Static digest files saved to `artifacts/`. |
| **Database queries** | `src/repo.py` | All SQLite access. No raw SQL elsewhere. |
| **Business logic** | `src/scoring.py`, `src/explain.py`, etc. | Pure functions, testable in isolation. |
| **Pydantic models** | `src/schemas.py` | Request/response models, validation. |
| **External APIs** | `src/clients/*.py` | Isolated clients with clear interfaces. |

### Anti-Patterns (DO NOT DO)

| Bad Pattern | Why It's Bad | Correct Approach |
|-------------|--------------|------------------|
| Inline HTML in `main.py` | Hard to maintain, can't use template inheritance | Use `templates/*.html` with `TemplateResponse` |
| Raw SQL in route handlers | Scattered DB logic, hard to test | Call `repo.py` functions |
| Business logic in routes | Routes become bloated, untestable | Extract to dedicated modules |
| Display logic in routes | UI changes require editing routes | Use `views.py` for view models |
| Duplicate HTML rendering | Two systems doing same thing | Consolidate or clearly separate purposes |

### Template Pattern

Routes that return HTML should follow this pattern:

```python
# In main.py
@app.get("/ui/page", response_class=HTMLResponse)
def ui_page(request: Request):
    # 1. Fetch data from repo
    conn = get_conn()
    try:
        data = get_something(conn)
    finally:
        conn.close()

    # 2. Return template response (NO inline HTML)
    return templates.TemplateResponse(
        request,
        "page.html",
        {"data": data}
    )
```

### Two HTML Systems (Intentional)

We have two HTML generation systems for different purposes:

1. **`templates/`** → Dynamic web UI (served by FastAPI)
   - Uses Jinja2 inheritance (`_base.html`)
   - Interactive features (feedback buttons, etc.)
   - Real-time data from database

2. **`artifacts.py`** → Static digest files (saved to disk)
   - Self-contained HTML files in `artifacts/`
   - Generated by batch jobs
   - Can be viewed offline or shared

These are intentionally separate. Do not merge them.

## Testing

Tests use isolated temp SQLite via `conftest.py` autouse fixture that sets `NEWS_DB_PATH`. All tests are deterministic with fixed timestamps and fixture data.

### Testing Patterns

Before writing new tests:
1. **Check existing tests** for established patterns (imports, fixtures, assertions)
2. **Add to existing test files** if testing related functionality
3. **Create new test file** only if testing a distinct module or feature

Test file organization:
- `test_repo.py` — database/repo layer tests
- `test_demo_flow.py` — API endpoint tests (routes, responses)
- `test_pipeline.py` — batch job integration tests
- `test_llm_openai.py` — LLM client tests
- `test_scoring.py` — ranking algorithm tests

## After Implementing Features (MANDATORY)

After ANY code change that adds new functionality, Claude MUST:

1. **Run `make test`** - verify existing tests pass
2. **Ask: "Does this change need new tests?"**
   - New function or endpoint? → Add unit test
   - New error path or refusal? → Add test for that path
   - Changed output format? → Update existing tests
   - New user-facing behavior? → Consider eval case
3. **If yes, write tests** before marking the task complete
4. **Run `make test` again** to verify new tests pass
5. **Update DEBUG_GUIDE.md** with what changed

**Test coverage checklist:**
- [ ] New functions have at least one test
- [ ] Error paths are tested (not just happy path)
- [ ] New fields in responses are verified in tests
- [ ] Logging events are tested if critical

**UI changes checklist:**
- [ ] New routes/pages? → Add to `ui_smoke` MCP tool
- [ ] Changed URL patterns? → Update `ui_smoke` regex
- [ ] Changed link structure? → Update `ui_smoke` checks
- [ ] Just styling/content? → No MCP update needed

This is NON-NEGOTIABLE. Do not skip this step.

## Pre-Merge Acceptance Checklist (MANDATORY)

Before a branch can be merged, Patrick must confirm:

- [ ] Tests are green
- [ ] UI manually clicked (happy path + refusal case)
- [ ] No debug/operator data leaked to customer UI
- [ ] Diff reviewed top-to-bottom
- [ ] I can explain the change in 2 sentences

If any box is unchecked, the branch is not merged.

## AI Engineering Patterns (AUTHORITATIVE)

These patterns are non-negotiable for all LLM-related code. They exist because trust, debuggability, and determinism matter more than convenience.

### 1. Structured Outputs via Pydantic

All LLM outputs must be parsed into Pydantic models with validators.

```python
# Good: Schema enforces contract
class SummaryResult(BaseModel):
    summary: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    refusal: str | None = None

    @model_validator(mode='after')
    def check_summary_or_refusal(self):
        # Either summary+citations OR refusal, never both, never neither
```

**Why:** LLMs produce unpredictable outputs. Schema validation catches malformed responses before they propagate.

### 2. Either-Or Contracts (XOR Pattern)

LLM adapter outputs must be **mutually exclusive**: either success data OR a refusal code.

```python
# Contract: (summary + citations) XOR refusal
if has_summary and has_refusal:
    raise ValueError("Cannot have both")
if not has_summary and not has_refusal:
    raise ValueError("Must have one")
```

**Why:** Ambiguous states create debugging nightmares. Explicit either-or makes behavior predictable.

### 3. Grounding as Trust Boundary

Every factual claim must be traceable to source evidence via **exact substring match**.

```python
# In grounding.py - THE trust boundary
for citation in result.citations:
    if citation.evidence_snippet not in evidence:
        return SummaryResult(refusal=GROUNDING_FAIL)
```

**Why:** Paraphrased citations can introduce hallucinations. Exact match is the only verifiable standard.

### 4. Refusal Taxonomy (Stable Error Codes)

Refusals use **stable, enumerated codes** - never free-form strings.

```python
# In error_codes.py
LLM_PARSE_FAIL = "LLM_PARSE_FAIL"    # JSON didn't match schema
LLM_API_FAIL = "LLM_API_FAIL"        # Timeout, 429, network
NO_EVIDENCE = "NO_EVIDENCE"          # Nothing to ground on
GROUNDING_FAIL = "GROUNDING_FAIL"    # Citation not in evidence
```

**Why:** Stable codes enable aggregation, alerting, and debugging. "Something went wrong" is useless.

### 5. Never Raise, Always Return

LLM adapters must handle all failure modes internally and return valid objects.

```python
# Good: Contract guarantees valid return
def summarize(item, evidence) -> tuple[SummaryResult, dict]:
    """ALWAYS returns SummaryResult (never raises)"""
    if not OPENAI_API_KEY:
        return _refuse(LLM_DISABLED)  # Valid refusal, not exception
```

**Why:** Exceptions propagate unpredictably. Return values are explicit and testable.

### 6. Evals as Safety Net (Pure Checks)

Eval functions **observe and report** - they never modify data.

```python
# In summary_checks.py
def check_citations_grounded(result, evidence) -> str | None:
    """Returns failure code or None. NEVER modifies result."""
    if citation.evidence_snippet not in evidence:
        return SNIPPET_NOT_GROUNDED
    return None
```

**Why:** Evals must be trustworthy. Side effects would make them unreliable.

### 7. Deterministic Caching

Cache keys are **content-addressed** (SHA256 of inputs). Cache only what affects output.

```python
# Good: Only model + evidence determine output
def compute_cache_key(model: str, evidence: str) -> str:
    raw = f"{model}|{normalize_evidence(evidence)}"
    return hashlib.sha256(raw.encode()).hexdigest()

# Bad: Including title/URL would cause unnecessary cache misses
```

**Why:** Deterministic keys prevent cache pollution. Normalize inputs to avoid spurious misses.

### 8. Temperature Zero for Determinism

Use `temperature=0.0` for all factual/grounded tasks.

```python
payload = {
    "model": MODEL,
    "temperature": 0.0,  # Determinism over creativity
    "max_tokens": 500
}
```

**Why:** Non-zero temperature introduces randomness. Grounded summaries must be reproducible.

### 9. Cost and Latency Observability

Every LLM call must log: tokens, cost, latency, status.

```python
log_event("llm_call",
    model=MODEL,
    prompt_tokens=usage["prompt_tokens"],
    completion_tokens=usage["completion_tokens"],
    cost_usd=round(cost, 6),
    latency_ms=latency,
    status="ok"
)
```

**Why:** LLM costs compound. You can't optimize what you don't measure.

### 10. Separation of Concerns

| Module | Responsibility | Does NOT do |
|--------|----------------|-------------|
| `llm_openai.py` | API calls, JSON parsing, retries | Grounding validation |
| `grounding.py` | Citation verification | API calls |
| `cache_utils.py` | Cache key computation, TTL | Storage (that's repo.py) |
| `summary_checks.py` | Eval checks | Modifying data |

**Why:** Each module has one job. Cross-cutting concerns create debugging nightmares.

### Anti-Patterns (DO NOT DO)

| Bad Pattern | Why It's Bad | Correct Approach |
|-------------|--------------|------------------|
| Free-form refusal strings | Can't aggregate or alert | Use stable error codes |
| Paraphrased citations | Can't verify grounding | Exact substring match only |
| Raising exceptions from LLM code | Unpredictable propagation | Return valid objects with refusal |
| temperature > 0 for facts | Non-deterministic outputs | temperature=0.0 |
| Caching by URL/title | Spurious cache misses | Cache by evidence content only |
| Modifying data in evals | Evals become untrustworthy | Pure functions only |

---

## Living Documentation (META-RULE)

CLAUDE.md is a **living document**. When important patterns emerge during implementation:

1. **Capture immediately** - Don't wait for "documentation day"
2. **Add to the right section** - Architecture, AI Engineering, Anti-Patterns, etc.
3. **Include the "why"** - Patterns without rationale get ignored
4. **Keep it authoritative** - This file wins over chat memory

**Trigger phrases for updates:**
- "This is a pattern we should document"
- "Add this to CLAUDE.md"
- "This mistake should be in the anti-patterns"

Claude should proactively suggest CLAUDE.md updates when discovering:
- Recurring bugs with the same root cause
- Architectural decisions that affect multiple files
- New trust boundaries or validation rules
- Cost/performance lessons learned

---

## Operability Conventions

- All responses include `X-Request-ID` header
- Errors return RFC 7807 ProblemDetails JSON
- Structured JSON logging via `log_event()`
- Run tracking: every operation gets a `run_id` with start/finish timestamps and metrics

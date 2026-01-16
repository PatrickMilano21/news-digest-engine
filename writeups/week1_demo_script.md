# Week 1 Demo Script — News Digest Engine (3–5 min)

## What this is (10–15s)
This is a deterministic, production-shaped news digest pipeline. It ingests items, normalizes + dedupes, persists to SQLite, tracks explicit runs, ranks deterministically with explainability, and produces a human-readable HTML digest artifact. The same pipeline can be run as a job or served via the API.

## Demo flow (60–90s)
1) Run the pipeline for a day:
- `make run DATE=2026-01-15`
This creates a run record and writes an artifact to `artifacts/digest_2026-01-15.html`.

2) Open the UI launcher for the date:
- `/ui/date/2026-01-15`
From here I can click directly into the artifact, the latest run, and the per-run debug endpoint.

3) Open the artifact:
- `/artifacts/digest_2026-01-15.html`
This shows run metadata (run_id, status, counts, timestamps) plus ranked items. Each item includes a “Why ranked” section that explains scoring inputs.

4) Check run metadata:
- `GET /runs/latest`
This returns the latest run record as JSON so the run state is machine-readable.

5) Open debug view for a specific run:
- `GET /debug/run/{run_id}`
This returns the run row plus the derived artifact path for quick ops navigation.

6) Validate system invariants:
- `make test`
Tests lock determinism, explainability output shape, and API contracts.

## How debugging works (45–60s)
- Every request gets a `request_id` (X-Request-ID header) for correlation.
- Runs get a `run_id` that ties together ingestion results and artifact output.
- If anything looks wrong, I can:
  1) open `/runs/latest` to see status + counts
  2) open `/debug/run/{run_id}` to inspect that run and jump to the artifact
  3) rely on tests to catch nondeterminism and output-shape regressions.

## Screenshot
- `writeups/week1_digest_screenshot.png`

## Three bullets (close)
**What I built:**
- Deterministic ingest → dedupe → persist → run tracking → ranking → explainability → HTML artifact, with job + API reuse.

**Tradeoffs:**
- SQLite + fixtures-first for determinism; real feed ingestion is modular but not the focus of Week 1. UI is intentionally minimal.

**What I’d do next:**
- Make daily_run ingest fixture feeds into non-empty digests by default, then add a user-configurable digest config (RankConfig) and an eval harness to measure ranking quality.

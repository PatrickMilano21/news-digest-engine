# news-digest-engine

A small FastAPI service that will ingest news feeds, normalize/dedupe items, and produce a daily digest.
Week 0 focus: zero-friction dev loop + operability defaults (request_id, structured logs, consistent errors).

## Quickstart

### Setup
Create venv + install deps (already done locally):
- `.venv/` is the per-repo environment.

### Run tests
```powershell
make test
```
  ## Scoreboard

  | Metric | Value | Date | Source |
  |--------|-------|------|--------|
  | Eval pass rate | 100% (50/50) | 2026-01-18 | `make eval DATE=2026-01-15` |
  | Run failure rate | 34% (10/29) | 2026-01-18 | `runs` table |

  ### Update commands

  ```powershell
  # Eval pass rate
  make eval DATE=YYYY-MM-DD

  # Run stats (one-liner)
  python -c "from src.db import get_conn, init_db; c=get_conn(); init_db(c); print(c.execute('SELECT status, COUNT(*) FROM   
  runs GROUP BY status').fetchall())"
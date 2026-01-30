PY := .\.venv\Scripts\python.exe

.PHONY: dev test run eval weights lint

dev:
	$(PY) -m uvicorn src.main:app --reload --port 8001

test:
	$(PY) -m pytest -q

run:
	$(PY) -m jobs.daily_run --date $(DATE) --mode fixtures
	$(PY) -m jobs.build_digest --date $(DATE)

eval:
	@if "$(DATE)"=="" (echo ERROR: missing DATE. Usage: make eval DATE=YYYY-MM-DD & exit /b 1)
	$(PY) -m src.eval --date $(DATE)

weights:
	@if "$(DATE)"=="" (echo ERROR: missing DATE. Usage: make weights DATE=YYYY-MM-DD & exit /b 1)
	$(PY) -m jobs.update_weights --date $(DATE)

lint:
	$(PY) -m ruff check .

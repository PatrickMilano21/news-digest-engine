PY := .\.venv\Scripts\python.exe

.PHONY: dev test run eval

dev:
	$(PY) -m uvicorn src.main:app --reload --port 8000

test:
	$(PY) -m pytest -q

run:
	python -m jobs.daily_run --date $(DATE) --mode fixtures
	python -m jobs.build_digest --date $(DATE)

eval:
	@if "$(DATE)"=="" (echo ERROR: missing DATE. Usage: make eval DATE=YYYY-MM-DD & exit /b 1)
	$(PY) -m src.eval --date $(DATE)

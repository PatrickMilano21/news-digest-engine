PY := .\.venv\Scripts\python.exe

.PHONY: dev test run eval

dev:
	$(PY) -m uvicorn src.main:app --reload --port 8000

test:
	$(PY) -m pytest -q

run:
	@if "$(DATE)"=="" (echo ERROR: missing DATE. Usage: make run DATE=YYYY-MM-DD & echo Example: make run DATE=2026-01-09 & exit /b 1)
	$(PY) -m src.run --date $(DATE)

eval:
	@if "$(DATE)"=="" (echo ERROR: missing DATE. Usage: make eval DATE=YYYY-MM-DD & exit /b 1)
	$(PY) -m src.eval --date $(DATE)

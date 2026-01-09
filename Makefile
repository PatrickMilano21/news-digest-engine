PY=.\.venv\Scripts\python.exe

dev:
	$(PY) -m uvicorn src.main:app --reload --port 8000

test:
	$(PY) -m pytest -q

run:
	@echo TODO: make run DATE=YYYY-MM-DD

eval:
	@echo TODO: make eval DATE=YYYY-MM-DD


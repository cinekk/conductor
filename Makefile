.PHONY: dev test lint typecheck

dev:
	uv run uvicorn conductor.main:app --reload --host 0.0.0.0 --port 8000

test:
	uv run pytest -v

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy conductor/

fmt:
	uv run ruff format .
	uv run ruff check --fix .

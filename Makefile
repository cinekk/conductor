.PHONY: dev dev-linear test lint typecheck fmt

dev:
	uv run uvicorn conductor.main:app --reload --host 0.0.0.0 --port 8000

dev-linear:
	@test -n "$$LINEAR_API_KEY" || (echo "Set LINEAR_API_KEY, LINEAR_TEAM_ID, LINEAR_WEBHOOK_SECRET first" && exit 1)
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

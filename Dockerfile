# syntax=docker/dockerfile:1
FROM python:3.14-slim AS base

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install dependencies in a cached layer (only re-runs if lock file changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application code
COPY conductor/ ./conductor/

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "conductor.main:app", "--host", "0.0.0.0", "--port", "8000"]

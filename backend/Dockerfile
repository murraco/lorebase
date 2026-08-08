# syntax=docker/dockerfile:1

# --- Build stage: resolve and install dependencies with uv ---
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Install dependencies first, separately from app code, so this layer stays
# cached across code changes and only re-runs when pyproject.toml/uv.lock change.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# --- Runtime stage: slim image, no uv/build tools ---
FROM python:3.13-slim-bookworm

RUN groupadd --system app && useradd --system --gid app app

COPY --from=builder --chown=app:app /app /app

ENV PATH="/app/.venv/bin:$PATH"
# The `app` user has no home directory (--system, no -m/-d) — Hugging
# Face's cache defaults to ~/.cache, which would resolve somewhere
# unwritable. Pointed explicitly at a path under /app, which is already
# chowned to app:app, and mounted as a named volume in docker-compose.yml
# so the (multi-hundred-MB) reranker model persists across restarts
# instead of re-downloading every time.
ENV HF_HOME=/app/.cache/huggingface
WORKDIR /app

USER app

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

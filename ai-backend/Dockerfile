# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

# Build context is the REPO ROOT — the uv workspace lockfile and the ingestion
# member live outside ai-backend/:
#   docker build -f ai-backend/Dockerfile .
#
# Chat service only: --package installs this member plus wahlchat-common, and
# leaves the ingestion member (and its connector tree) out.
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app
# Layer 1: third-party dependencies only (cached unless a pyproject/uv.lock
# changes). --no-install-workspace is REQUIRED here: without it uv tries to
# build the workspace members, and hatchling fails because their sources are
# not yet in the image.
COPY pyproject.toml uv.lock ./
COPY ai-backend/pyproject.toml ai-backend/pyproject.toml
COPY ingestion/pyproject.toml ingestion/pyproject.toml
COPY packages/wahlchat-common/pyproject.toml packages/wahlchat-common/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-workspace --package wahl-chat-backend

# Layer 2: the members themselves (re-runs only when sources change).
# READMEs are copied because both pyprojects declare readme = "README.md",
# which hatchling reads at build time. .dockerignore keeps .env*, tests/ and
# caches out of the build context.
COPY ai-backend/README.md ai-backend/README.md
COPY packages/wahlchat-common/README.md packages/wahlchat-common/README.md
COPY ai-backend/src /app/ai-backend/src
COPY packages/wahlchat-common/src /app/packages/wahlchat-common/src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --package wahl-chat-backend

# Runtime stage — no uv, no build tools, non-root user.
FROM python:3.12-slim AS runtime
RUN useradd --create-home --uid 1000 appuser
COPY --from=builder --chown=appuser:appuser /app /app
# WORKDIR is ai-backend/ so relative paths resolve as they do in local dev
# (`cd ai-backend && python -m src.app`).
WORKDIR /app/ai-backend
ENV PATH="/app/.venv/bin:$PATH"
USER appuser

# Single role: the FastAPI chat service. Ingestion is a separate image, so a
# job spec can no longer boot this by mistake and vice versa.
ENTRYPOINT ["sh", "-c", "exec python -m src.app --host 0.0.0.0 --port ${PORT:-8080}"]

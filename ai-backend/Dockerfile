# SPDX-FileCopyrightText: 2025 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app
# Layer 1: dependencies only (cached unless pyproject.toml/uv.lock change).
# --no-install-project is REQUIRED here: without it uv tries to build the root
# project, and hatchling fails because README.md/src are not yet in the image.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

# Layer 2: the project itself (re-runs only when sources change).
# .dockerignore keeps .env*, tests/ and caches out of the build context.
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev
# Ensure the dispatch entrypoint is executable regardless of the host's mode bits.
RUN chmod +x /app/docker-entrypoint.sh

# Runtime stage — no uv, no build tools, non-root user.
FROM python:3.12-slim AS runtime
RUN useradd --create-home --uid 1000 appuser
COPY --from=builder --chown=appuser:appuser /app /app
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"
USER appuser

# Single image serves both roles; the entrypoint dispatches on CONNECTOR_ID:
#   - unset  → FastAPI app (web service, the default)
#   - set    → src.ingestion.run for that connector (Cloud Run ingestion Job)
# So the ingestion Job only sets CONNECTOR_ID (see infra/README.md) — no
# container-command override, and the job can never boot the API by mistake.
ENTRYPOINT ["/app/docker-entrypoint.sh"]

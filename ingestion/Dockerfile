# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

# Build context is the REPO ROOT — the uv workspace lockfile lives there:
#   docker build -f ingestion/Dockerfile .
#
# Corpus-layer image for the scheduled Cloud Run Jobs: no fastapi/uvicorn,
# no firebase-admin, no chat-service code. ai-backend/pyproject.toml is copied
# only because uv needs every member's manifest to resolve the shared lock;
# --package installs this member plus wahlchat-common, never the backend.
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app
# Layer 1: third-party dependencies only (cached unless a pyproject/uv.lock
# changes). --no-install-workspace is REQUIRED here: without it uv tries to
# build the members, and hatchling fails because their sources are not yet in
# the image.
COPY pyproject.toml uv.lock ./
COPY ai-backend/pyproject.toml ai-backend/pyproject.toml
COPY ingestion/pyproject.toml ingestion/pyproject.toml
COPY packages/wahlchat-common/pyproject.toml packages/wahlchat-common/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-workspace --package ingestion

# Layer 2: the ingestion member itself (re-runs only when sources change).
# README.md is copied because pyproject declares readme = "README.md", which
# hatchling reads at build time. data/ carries the manifesto_uploads manifests;
# MdB-Stammdaten is excluded by .dockerignore and fetched at run time.
COPY ingestion/README.md ingestion/README.md
COPY packages/wahlchat-common/README.md packages/wahlchat-common/README.md
COPY ingestion/src /app/ingestion/src
COPY packages/wahlchat-common/src /app/packages/wahlchat-common/src
COPY ingestion/data /app/ingestion/data
COPY ingestion/docker-entrypoint.sh /app/ingestion/docker-entrypoint.sh
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --package ingestion
# Executable regardless of the host's mode bits.
RUN chmod +x /app/ingestion/docker-entrypoint.sh

# Runtime stage — no uv, no build tools, non-root user.
FROM python:3.12-slim AS runtime
RUN useradd --create-home --uid 1000 appuser
COPY --from=builder --chown=appuser:appuser /app /app
# WORKDIR is ingestion/ so the connectors' CWD-relative paths (data/) resolve
# exactly as they do in local dev (`cd ingestion && python -m ingestion.run`).
WORKDIR /app/ingestion
ENV PATH="/app/.venv/bin:$PATH"
USER appuser

# The Job spec sets CONNECTOR_ID (run.py reads it directly); extra runner flags
# such as --batch-size / --time-budget may be passed as container args.
ENTRYPOINT ["/app/ingestion/docker-entrypoint.sh"]

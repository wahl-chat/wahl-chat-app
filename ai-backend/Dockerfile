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

# Runtime stage — no uv, no build tools, non-root user.
FROM python:3.12-slim AS runtime
RUN useradd --create-home --uid 1000 appuser
COPY --from=builder --chown=appuser:appuser /app /app
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"
USER appuser

# Entry point: FastAPI app (D-04 — aiohttp_app replaced in plan 01-06)
# Web image: docker build -t wahlchat-web . (default CMD)
CMD ["python", "-m", "src.app", "--host", "0.0.0.0", "--port", "8080"]

# ---------------------------------------------------------------------------
# Production ingestion entrypoint (D-03 — same image, CONNECTOR_ID selects).
# To run as the ingestion image, override CMD at docker run / job spec:
#
#   docker run --env CONNECTOR_ID=bundestag_votes wahlchat-ingestion
#   gcloud run jobs create ... --set-env-vars "CONNECTOR_ID=bundestag_votes"
#
# The runner reads CONNECTOR_ID (or --connector arg) and dispatches to the
# matching connector factory in src.ingestion.registry (D-03).
#
# Ingestion image: docker build --build-arg ENTRYPOINT=ingestion -t wahlchat-ingestion .
# ---------------------------------------------------------------------------
# CMD ["python", "-m", "src.ingestion.run"]

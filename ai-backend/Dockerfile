# SPDX-FileCopyrightText: 2025 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.3 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime
COPY --from=builder /app/.venv /app/.venv
COPY . /app
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"

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

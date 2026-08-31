# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
FastAPI application entry point.

Transport: SSE via sse-starlette.
"""

import argparse
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routes import chat, pro_con, voting_behavior, misc
from src.utils import get_cors_allowed_origins

LOGGING_FORMAT = (
    "%(asctime)s - %(name)s - %(filename)s - %(lineno)d - %(levelname)s - %(message)s"
)
logging.basicConfig(level=logging.INFO, format=LOGGING_FORMAT)
logger = logging.getLogger(__name__)


def _corpus_rollout_gate_enabled() -> bool:
    return os.getenv("REQUIRE_CORPUS", "").strip().lower() in ("1", "true", "yes")


def enforce_corpus_rollout_gate() -> None:
    """Explicit rollout gate: refuse to boot on a corpus that isn't populated yet.

    The V2 corpus (``wahlchat_chunks_{ENV}``) is filled by scheduled ingestion
    plus a one-time snapshot backfill that are provisioned separately (see
    infra/README.md). Until a deployment has actually populated it, serving chat
    would ground every answer in an empty store. Deployments opt into enforcement
    with ``REQUIRE_CORPUS=true`` — the corpus-cutover step flips it on in prod
    once ingestion + bootstrap exist. Unset (local dev, CI, tests) → no-op, so an
    empty local store still boots for development.
    """
    if not _corpus_rollout_gate_enabled():
        return
    # Deferred import: setup_collection allocates nothing at import time, but the
    # count call below constructs a QdrantClient we only want on the gated path.
    from wahlchat_corpus.corpus import COLLECTION_NAME, corpus_point_count

    count = corpus_point_count()
    if not count:
        raise RuntimeError(
            f"REQUIRE_CORPUS is set but the corpus collection {COLLECTION_NAME!r} "
            f"is {'missing' if count is None else 'empty'} — refusing to start. "
            "Populate it via the scheduled ingestion jobs + snapshot backfill "
            "before switching the runtime to corpus-grounded chat "
            "(see infra/README.md)."
        )
    logger.info("Corpus rollout gate OK: %s has %d point(s).", COLLECTION_NAME, count)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    enforce_corpus_rollout_gate()
    yield


app = FastAPI(
    title="wahl.chat API",
    description="Political information chatbot backend — SSE streaming transport",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS: enumerated origins only — get_cors_allowed_origins never returns "*"
# (allow_credentials=True below would otherwise reflect any Origin with
# credentials). Extra deploy-specific origins come from CORS_EXTRA_ORIGINS.
cors_origins = get_cors_allowed_origins(os.getenv("ENV"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_headers=["*"],
    allow_methods=["*"],
)

logger.info(f"CORS allowed origins: {cors_origins}")

# Routers — all prefixed with /api/v1
app.include_router(chat.router)
app.include_router(pro_con.router)
app.include_router(voting_behavior.router)
app.include_router(misc.router)


@app.get("/healthz")
async def health_check():
    """Kubernetes / CI health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(description="wahl.chat FastAPI backend")
    parser.add_argument("--host", type=str, nargs=1, default=["127.0.0.1"])
    parser.add_argument("--port", type=int, nargs=1, default=[8080])
    parser.add_argument("--debug", action="store_true", default=False)
    args = parser.parse_args()

    host = args.host[0]
    port = args.port[0]

    if args.debug:
        for log_name, log_obj in logging.Logger.manager.loggerDict.items():
            if isinstance(log_obj, logging.Logger) and log_name.startswith("src"):
                log_obj.setLevel(logging.DEBUG)

    uvicorn.run("src.app:app", host=host, port=port, reload=False)

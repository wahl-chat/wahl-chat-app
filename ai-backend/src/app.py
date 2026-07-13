# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
FastAPI entry point — replaces the V1 aiohttp entry point.

Transport: SSE via sse-starlette.
"""

import argparse
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routes import chat, pro_con, voting_behavior, misc
from src.utils import get_cors_allowed_origins

LOGGING_FORMAT = (
    "%(asctime)s - %(name)s - %(filename)s - %(lineno)d - %(levelname)s - %(message)s"
)
logging.basicConfig(level=logging.INFO, format=LOGGING_FORMAT)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="wahl.chat API",
    description="Political information chatbot backend — SSE streaming transport",
    version="2.0.0",
)

# CORS: allow only known origins
cors_allowed_origins = get_cors_allowed_origins(os.getenv("ENV"))
if isinstance(cors_allowed_origins, str):
    cors_origins = [cors_allowed_origins]
else:
    cors_origins = cors_allowed_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_headers=["*"],
    allow_methods=["*"],
)

logger.info(f"CORS allowed origins: {cors_origins}")

# Routers — all prefixed with /api/v1 (preserved from V1 route_prefix convention)
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

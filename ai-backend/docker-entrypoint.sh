#!/bin/sh
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
#
# One image, two roles. A Cloud Run Job sets CONNECTOR_ID and runs the ingestion
# runner; the web service leaves it unset and runs the FastAPI app. Dispatching
# on CONNECTOR_ID here means a job spec cannot accidentally boot the API server
# instead of the connector (the failure this guards against) — the job only has
# to set CONNECTOR_ID, no container-command override required.
set -eu

if [ -n "${CONNECTOR_ID:-}" ]; then
    # Extra runner flags (e.g. --batch-size, --time-budget) may be passed as
    # container args; forward them.
    exec python -m src.ingestion.run "$@"
fi

exec python -m src.app --host 0.0.0.0 --port "${PORT:-8080}"

#!/usr/bin/env bash
# Strict mode — uncomment when actually deploying (kept commented while this
# script is AUTHORED, NOT APPLIED so sourcing/reviewing it can never exit a shell):
# set -euo pipefail
# =============================================================================
# AUTHORED, NOT APPLIED — do NOT run gcloud deploy/apply.
#
# Cloud Run Jobs + Cloud Scheduler IaC for wahl.chat V2 ingestion connectors.
#
# Reconciled to the surviving connector
# (abgeordnetenwatch_votes). Removed connectors and GCS/Firestore
# env wiring deleted. Connectors now need only:
#   QDRANT_URL + OPENAI_API_KEY + EU region (Qdrant-only single-store runtime).
#
# Purpose:
#   Author the GCP configuration for the surviving ingestion connector so
#   that the "scheduled Cloud Run Jobs in an EU region" requirement
#   is satisfied by having the config committed — even though
#   no gcloud commands are executed here.
#
# Design:
#   - ONE shared Docker image (same image for every connector)
#   - CONNECTOR_ID env var selects which connector the runner invokes
#   - Single task per job execution; --task-timeout 3600 (1h >> Firebase 15-min cap)
#   - EU residency: REGION=europe-west1 (data-residency constraint)
#   - One Cloud Run Job + one Cloud Scheduler trigger per connector
#
# To actually deploy (manual EU operator step):
#   1. Authenticate: gcloud auth login && gcloud config set project $PROJECT
#   2. Build and push the image to Artifact Registry
#   3. Run this script (uncomment `set -euo pipefail` for strict mode)
#
# Security:
#   - No inline secrets — all sensitive values come from env vars or SA references
#   - Service account email passed as $RUN_INVOKER_SA (never hardcoded here)
# =============================================================================

# --- Configuration -----------------------------------------------------------

# PROJECT: GCP project ID (set before running)
PROJECT="${PROJECT:-wahl-chat-prod}"

# REGION: EU-residency region (data-residency constraint — never change to non-EU)
REGION="europe-west1"

# IMAGE: Artifact Registry image for the ingestion container (single image)
IMAGE="${IMAGE:-${REGION}-docker.pkg.dev/${PROJECT}/wahlchat/ingestion:latest}"

# RUN_INVOKER_SA: Service account that Cloud Scheduler uses to invoke the job run endpoint
RUN_INVOKER_SA="${RUN_INVOKER_SA:-run-invoker@${PROJECT}.iam.gserviceaccount.com}"

# QDRANT_URL: Qdrant vector store URL (prod — Qdrant-only single-store runtime)
QDRANT_URL="${QDRANT_URL:-https://qdrant.wahl-chat-prod.internal:6333}"

# --- Cloud Run Jobs ----------------------------------------------------------
#
# One job per connector, same image, CONNECTOR_ID env var selects the connector.
# Tasks = 1 (single-task per job; task-sharding deferred).
# Task timeout = 3600s (1 hour — far exceeds Firebase Scheduled Functions 15-min cap;
# Firebase's 15-min limit does NOT apply to Cloud Run Jobs which support up to 24h).
#
# Connector (one surviving — others removed):
#   abgeordnetenwatch_votes → daily (parliament votes published nightly)

for CONN in abgeordnetenwatch_votes; do
  # Job NAME must match Cloud Run's [a-z]([-a-z0-9]*[a-z0-9])? — no underscores,
  # so connector-id underscores become hyphens. CONNECTOR_ID env var keeps
  # the underscore form: it is the registry key the runner resolves.
  #
  # `deploy` (not `create`) is idempotent: it creates the job on first run and
  # updates it on re-runs, so this script can be re-applied safely.
  gcloud run jobs deploy "wahlchat-${CONN//_/-}" \
    --image "${IMAGE}" \
    --region "${REGION}" \
    --set-env-vars "CONNECTOR_ID=${CONN},ENV=prod,QDRANT_URL=${QDRANT_URL}" \
    --set-secrets "OPENAI_API_KEY=openai-api-key:latest" \
    --task-timeout 3600 \
    --max-retries 1 \
    --tasks 1 \
    --project "${PROJECT}"
    # Add when the connector needs an Abgeordnetenwatch API key (rate limits):
    # --set-secrets "AW_API_KEY=aw-api-key:latest" \
done

# --- Cloud Scheduler triggers ------------------------------------------------
#
# One scheduler trigger per job.
# The trigger sends an HTTP POST to the Cloud Run Jobs `:run` endpoint.
# OAuth service account is referenced by variable, never hardcoded.
#
# Schedule examples (adjust to actual requirements):
#   abgeordnetenwatch_votes → 04:00 daily (parliament votes published nightly)

# The :run URI references the Cloud Run job by its hyphenated name (must
# match the `gcloud run jobs deploy` name above, never the underscore form).
gcloud scheduler jobs create http "wahlchat-abgeordnetenwatch-votes-cron" \
  --location "${REGION}" \
  --schedule "0 4 * * *" \
  --time-zone "Europe/Berlin" \
  --uri "https://run.googleapis.com/v2/projects/${PROJECT}/locations/${REGION}/jobs/wahlchat-abgeordnetenwatch-votes:run" \
  --http-method POST \
  --oauth-service-account-email "${RUN_INVOKER_SA}" \
  --project "${PROJECT}"

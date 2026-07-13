#!/usr/bin/env bash
# =============================================================================
# AUTHORED, NOT APPLIED this milestone (D-01) — do NOT run gcloud deploy/apply.
#
# Cloud Run Jobs + Cloud Scheduler IaC for wahl.chat V2 ingestion connectors.
#
# Phase 5 (D-09/D-10): reconciled to the two surviving connectors
# (abgeordnetenwatch_votes, pledgetracker). Removed connectors and GCS/Firestore
# env wiring deleted. Connectors now need only:
#   QDRANT_URL + OPENAI_API_KEY + EU region (Qdrant-only single-store runtime).
#
# Purpose:
#   Author the GCP configuration for the two surviving ingestion connectors so
#   that the "scheduled Cloud Run Jobs in an EU region" acceptance criterion
#   (INGEST-01) is satisfied by having the config committed — even though
#   no gcloud commands are executed this milestone (D-01).
#
# Design:
#   - ONE shared Docker image (same image for both connectors — D-03)
#   - CONNECTOR_ID env var selects which connector the runner invokes
#   - Single task per job execution (D-04); --task-timeout 3600 (1h >> Firebase 15-min cap)
#   - EU residency: REGION=europe-west1 (CLAUDE.md constraint)
#   - One Cloud Run Job + one Cloud Scheduler trigger per connector
#
# To actually deploy (future milestone — manual EU operator step):
#   1. Authenticate: gcloud auth login && gcloud config set project $PROJECT
#   2. Build and push the image to Artifact Registry
#   3. Run this script (uncomment `set -euo pipefail` for strict mode)
#
# Security:
#   - No inline secrets — all sensitive values come from env vars or SA references (T-03-15)
#   - Service account email passed as $RUN_INVOKER_SA (never hardcoded here)
# =============================================================================

# --- Configuration -----------------------------------------------------------

# PROJECT: GCP project ID (set before running)
PROJECT="${PROJECT:-wahl-chat-prod}"

# REGION: EU-residency region (CLAUDE.md constraint — never change to non-EU)
REGION="europe-west1"

# IMAGE: Artifact Registry image for the ingestion container (single image, D-03)
IMAGE="${IMAGE:-${REGION}-docker.pkg.dev/${PROJECT}/wahlchat/ingestion:latest}"

# RUN_INVOKER_SA: Service account that Cloud Scheduler uses to invoke the job run endpoint
RUN_INVOKER_SA="${RUN_INVOKER_SA:-run-invoker@${PROJECT}.iam.gserviceaccount.com}"

# QDRANT_URL: Qdrant vector store URL (prod — Qdrant-only single-store runtime, D-09)
QDRANT_URL="${QDRANT_URL:-https://qdrant.wahl-chat-prod.internal:6333}"

# --- Cloud Run Jobs ----------------------------------------------------------
#
# One job per connector, same image, CONNECTOR_ID env var selects the connector.
# Tasks = 1 (D-04 single-task per job; task-sharding deferred).
# Task timeout = 3600s (1 hour — far exceeds Firebase Scheduled Functions 15-min cap;
# Firebase's 15-min limit does NOT apply to Cloud Run Jobs which support up to 24h).
#
# Phase 5 connectors (two surviving — two others removed in D-09):
#   abgeordnetenwatch_votes → daily (parliament votes published nightly)
#   pledgetracker           → daily (Cambridge endpoint refreshes overnight)

for CONN in abgeordnetenwatch_votes pledgetracker; do
  gcloud run jobs create "wahlchat-${CONN}" \
    --image "${IMAGE}" \
    --region "${REGION}" \
    --set-env-vars "CONNECTOR_ID=${CONN},ENV=prod,QDRANT_URL=${QDRANT_URL}" \
    --task-timeout 3600 \
    --max-retries 1 \
    --tasks 1 \
    --project "${PROJECT}"
done

# --- Cloud Scheduler triggers ------------------------------------------------
#
# One scheduler trigger per job.
# The trigger sends an HTTP POST to the Cloud Run Jobs `:run` endpoint.
# OAuth service account is referenced by variable, never hardcoded (T-03-15).
#
# Schedule examples (adjust to actual requirements):
#   abgeordnetenwatch_votes → 04:00 daily (parliament votes published nightly)
#   pledgetracker           → 06:00 daily (Cambridge endpoint refreshes overnight)

gcloud scheduler jobs create http "wahlchat-abgeordnetenwatch_votes-cron" \
  --location "${REGION}" \
  --schedule "0 4 * * *" \
  --time-zone "Europe/Berlin" \
  --uri "https://run.googleapis.com/v2/projects/${PROJECT}/locations/${REGION}/jobs/wahlchat-abgeordnetenwatch_votes:run" \
  --http-method POST \
  --oauth-service-account-email "${RUN_INVOKER_SA}" \
  --project "${PROJECT}"

gcloud scheduler jobs create http "wahlchat-pledgetracker-cron" \
  --location "${REGION}" \
  --schedule "0 6 * * *" \
  --time-zone "Europe/Berlin" \
  --uri "https://run.googleapis.com/v2/projects/${PROJECT}/locations/${REGION}/jobs/wahlchat-pledgetracker:run" \
  --http-method POST \
  --oauth-service-account-email "${RUN_INVOKER_SA}" \
  --project "${PROJECT}"

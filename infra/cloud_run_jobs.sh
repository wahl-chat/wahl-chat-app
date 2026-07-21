#!/usr/bin/env bash
# =============================================================================
# AUTHORED, NOT APPLIED — do NOT run gcloud deploy/apply from here.
#
# Cloud Run Jobs + Cloud Scheduler config for the wahl.chat V2 ingestion
# connector (abgeordnetenwatch_votes). One shared image; the container
# entrypoint dispatches on CONNECTOR_ID (see ai-backend/docker-entrypoint.sh),
# so a job only sets env vars — no container-command override.
#
# `set -euo pipefail` stays commented while this file is authored-not-applied so
# sourcing/reviewing it cannot exit a shell. Uncomment it before a real deploy —
# the validation guards below rely on `set -e` to fail fast.
# set -euo pipefail
#
# To deploy (manual EU operator step):
#   1. gcloud auth login && gcloud config set project "$PROJECT"
#   2. Build and push the image to Artifact Registry.
#   3. Uncomment `set -euo pipefail`, export PROJECT/ENV/QDRANT_URL, run this.
#
# Later: replace this script with Terraform (Cloud Run Jobs + Scheduler + Secret
# Manager + Workload Identity) — tracked as a separate infra workstream.
# =============================================================================

# --- Configuration (all required; NO silent defaults for prod-affecting values) ---

# ENV: target environment — "dev" or "prod". Required.
ENV="${ENV:?set ENV=dev or ENV=prod}"

# PROJECT: GCP project ID. Required. Validated against ENV below so a prod deploy
# cannot accidentally target the wrong project (the actual prod project is
# "wahl-chat" — NOT "wahl-chat-prod").
PROJECT="${PROJECT:?set PROJECT to the target GCP project ID}"

case "$ENV" in
  prod)
    if [ "$PROJECT" != "wahl-chat" ]; then
      echo "ERROR: ENV=prod requires PROJECT=wahl-chat (got '$PROJECT')." >&2
      exit 1
    fi
    ;;
  dev)
    # Dev project id is operator-supplied; just refuse the known-wrong prod value.
    if [ "$PROJECT" = "wahl-chat" ]; then
      echo "ERROR: ENV=dev must not target the prod project 'wahl-chat'." >&2
      exit 1
    fi
    ;;
  *)
    echo "ERROR: ENV must be 'dev' or 'prod' (got '$ENV')." >&2
    exit 1
    ;;
esac

# REGION: EU-residency region (data-residency constraint — never change to non-EU).
REGION="europe-west1"

# IMAGE: Artifact Registry image for the ingestion container (single image).
IMAGE="${IMAGE:-${REGION}-docker.pkg.dev/${PROJECT}/wahlchat/ingestion:latest}"

# RUN_INVOKER_SA: service account Cloud Scheduler uses to invoke the job :run endpoint.
RUN_INVOKER_SA="${RUN_INVOKER_SA:-run-invoker@${PROJECT}.iam.gserviceaccount.com}"

# QDRANT_URL: Qdrant vector store URL for this env. Required — the protected
# store also needs an API key, injected from Secret Manager below.
QDRANT_URL="${QDRANT_URL:?set QDRANT_URL to the ${ENV} Qdrant endpoint}"

# LEGISLATURE_IDS: which AW parliament_period IDs to ingest, one Cloud Run Job
# each. MUST be set explicitly per job: with no AW_LEGISLATURE_ID the connector
# falls back to 111 (the 19th Bundestag), leaving the current Bundestag and every
# Landtag unpopulated. Default = 161 (current Bundestag, 21st WP); append the
# Landtag IDs from LANDTAG_LEGISLATURE_IDS in
# ai-backend/src/ingestion/connectors/abgeordnetenwatch/legislature_config.py:
#   LEGISLATURE_IDS="161 149 157 158 ..." ./cloud_run_jobs.sh
LEGISLATURE_IDS="${LEGISLATURE_IDS:-161}"

CONNECTOR_ID="abgeordnetenwatch_votes"

# --- Cloud Run Jobs (one per legislature id) ---------------------------------
#
# Same image; CONNECTOR_ID selects the connector and AW_LEGISLATURE_ID scopes it
# to one parliament. Task timeout 3600s (1h) far exceeds the 15-min scheduled-
# function cap. Secrets come from Secret Manager refs, never inline.

for LEGIS_ID in ${LEGISLATURE_IDS}; do
  # Cloud Run names must match [a-z]([-a-z0-9]*[a-z0-9])? — hyphens, no underscores.
  JOB_NAME="wahlchat-aw-votes-${LEGIS_ID}"
  gcloud run jobs deploy "${JOB_NAME}" \
    --image "${IMAGE}" \
    --region "${REGION}" \
    --set-env-vars "CONNECTOR_ID=${CONNECTOR_ID},ENV=${ENV},QDRANT_URL=${QDRANT_URL},AW_LEGISLATURE_ID=${LEGIS_ID}" \
    --set-secrets "OPENAI_API_KEY=openai-api-key:latest,QDRANT_API_KEY=qdrant-api-key:latest" \
    --task-timeout 3600 \
    --max-retries 1 \
    --tasks 1 \
    --project "${PROJECT}"
    # Add when the connector needs an Abgeordnetenwatch API key (rate limits):
    # --set-secrets "...,AW_API_KEY=aw-api-key:latest" \

  # --- Cloud Scheduler trigger for this job ---
  # POSTs to the Cloud Run Jobs :run endpoint at 04:00 Europe/Berlin (votes
  # publish nightly). The :run URI must reference the hyphenated job name.
  gcloud scheduler jobs create http "${JOB_NAME}-cron" \
    --location "${REGION}" \
    --schedule "0 4 * * *" \
    --time-zone "Europe/Berlin" \
    --uri "https://run.googleapis.com/v2/projects/${PROJECT}/locations/${REGION}/jobs/${JOB_NAME}:run" \
    --http-method POST \
    --oauth-service-account-email "${RUN_INVOKER_SA}" \
    --project "${PROJECT}"
done

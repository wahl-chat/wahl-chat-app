# infra/ — Cloud Run Jobs + Scheduler IaC

## Status: AUTHORED, NOT APPLIED

The scripts in this directory author the GCP Cloud Run Jobs and Cloud Scheduler
configuration for the wahl.chat V2 ingestion pipeline. **They are NOT executed
yet.** The requirement of "scheduled Cloud Run
Jobs in an EU region" is satisfied by committing this authored configuration;
actual deployment is deferred.

**Current state:** Reconciled to the surviving connector
(`abgeordnetenwatch_votes`). Obsolete connectors and all
GCS/Firestore env wiring removed; connectors now require only `QDRANT_URL` +
`OPENAI_API_KEY` (Qdrant-only single-store runtime).

> **Note:** The actual `gcloud run jobs deploy` execution against
> `europe-west1`/`europe-west3` is a manual operator IaC step out of this
> repo's automated scope (EU-residency + Firebase 15-min cap). This
> directory only commits the authored deploy artifacts.

---

## Contents

| File | Purpose |
|------|---------|
| `cloud_run_jobs.sh` | Creates one Cloud Run Job + one Scheduler trigger per connector, all in `europe-west1`. |

---

## Design Decisions

### EU Residency

All Cloud Run Jobs and Cloud Scheduler triggers use `REGION=europe-west1`
(Belgium, EU). This satisfies the GDPR Art. 9 EU data residency constraint
(`europe-west1`/`europe-west3`).

### Single Image, CONNECTOR_ID Selects

The connector (`abgeordnetenwatch_votes`) runs from the **same
Docker image** used for every ingestion connector. The `CONNECTOR_ID`
environment variable tells the runner (`src.ingestion.run`) which connector
to invoke:

```
CONNECTOR_ID=abgeordnetenwatch_votes → runs AbgeordnetenwatchVotesConnector via run_connector()
```

This is the same code path locally and in Cloud Run: locally you invoke
`uv run python -m src.ingestion.run --connector <id>`; in Cloud Run the job spec
sets the `CONNECTOR_ID` env var and the same entrypoint is the container CMD.

### Per-connector Scheduling

Each connector has its own Cloud Scheduler trigger pointing at its own Cloud Run Job.
This allows independent schedules (e.g. `abgeordnetenwatch_votes` daily at 04:00)
without coupling the connectors' run cadences.

### Single Task per Job

`--tasks 1` — Cloud Run task-sharding (`task-count > 1`) is a future scaling lever
and is explicitly deferred. Document `CLOUD_RUN_TASK_INDEX` as the future
shard-awareness hook; do NOT build it now.

### 1-Hour Task Timeout (not 15 minutes)

`--task-timeout 3600` sets a 1-hour per-task timeout. The 15-minute cap is a
**Firebase Scheduled Functions** limit, NOT a Cloud Run Jobs limit (Cloud Run Jobs
support up to 24 hours). Long connectors with a large backlog will stay within
1 hour; if they need longer, bump the timeout — no architectural change is
required.

### Qdrant-only Runtime

Connectors pass only `QDRANT_URL` (and `OPENAI_API_KEY` via Secret Manager).
All GCS bucket and Firestore emulator env vars removed — the old
two-phase enqueue→worker GCS/Firestore data paths were deleted.
The job now writes directly to Qdrant via run_connector().

---

## Local Equivalence

Running connectors locally is fully equivalent to Cloud Run execution. Use the
Makefile targets (root `Makefile`) which invoke the same `src.ingestion.run`
entrypoint against the local Qdrant container:

```bash
# Start local stores first
make stores-up

# Run connectors locally (Qdrant-only — no Firestore emulator needed)
make run-abgeordnetenwatch-votes
```

Or invoke directly:

```bash
QDRANT_URL=http://localhost:6333 uv run python -m src.ingestion.run --connector abgeordnetenwatch_votes
```

---

## How to Deploy (Manual EU Operator Step)

When the team is ready to deploy to GCP:

1. Authenticate and configure:
   ```bash
   gcloud auth login
   gcloud config set project <your-project-id>
   ```

2. Build and push the ingestion image:
   ```bash
   docker build -t europe-west1-docker.pkg.dev/<project>/wahlchat/ingestion:latest ai-backend/
   docker push europe-west1-docker.pkg.dev/<project>/wahlchat/ingestion:latest
   ```

3. Set required environment variables:
   ```bash
   export PROJECT=<your-project-id>
   export IMAGE=europe-west1-docker.pkg.dev/<project>/wahlchat/ingestion:latest
   export RUN_INVOKER_SA=run-invoker@<project>.iam.gserviceaccount.com
   export QDRANT_URL=https://qdrant.<project>.internal:6333
   ```

4. Run the IaC script (review it first — no `--dry-run` flag):
   ```bash
   bash infra/cloud_run_jobs.sh
   ```

> **Never commit API keys, passwords, or service-account JSON to this directory.**
> All sensitive values are passed via environment variables or referenced by
> service-account email.

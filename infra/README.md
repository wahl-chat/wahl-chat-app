# infra/ — deployment (planned via Terraform)

## Status: NOT YET IMPLEMENTED

Scheduled ingestion deployment — Cloud Run Jobs + Cloud Scheduler in an EU
region — is a dedicated future workstream, provisioned with Terraform
(declarative, reviewable, drift-free) alongside the CI / Workload Identity work.

Until it lands, ingestion runs through the **deployable container image** — the
same image the Cloud Run Jobs will use — driven manually via Docker Compose and
the Makefile. It can target either the local Qdrant container or a deployed
store, so a dev/prod corpus can be populated before the scheduler exists.

## Running ingestion before Cloud Run Jobs exist

The image dispatches on `CONNECTOR_ID` (`ai-backend/docker-entrypoint.sh`): unset
→ the FastAPI app; set → `src.ingestion.run` for that connector. Running the
image (rather than a host `uv` path) exercises the real deployable artifact.

```bash
# Local Qdrant (compose network), one connector:
docker compose --profile ingestion run --rm \
  -e CONNECTOR_ID=abgeordnetenwatch_votes ingestion

# A deployed store — override QDRANT_URL / QDRANT_API_KEY / ENV:
docker compose --profile ingestion run --rm \
  -e CONNECTOR_ID=abgeordnetenwatch_votes \
  -e QDRANT_URL=https://<host>:6333 -e QDRANT_API_KEY=<key> -e ENV=prod \
  ingestion
```

The host `uv run` Makefile targets (`make run-abgeordnetenwatch-votes`,
`make run-speeches`, …) remain for the fast dev loop and also honour
`QDRANT_URL` / `QDRANT_API_KEY` / `ENV` overrides.

**Collection bootstrap.** Both paths ensure the Qdrant collection exists before
ingesting: the entrypoint runs the idempotent `setup_collection` when
`CONNECTOR_ID` is set, and the Makefile targets depend on `bootstrap-collection`.
A fresh dev/prod Qdrant is therefore created on first run instead of 404ing on
the cursor read — no separate bootstrap step to remember.

**The speech connectors must run sequentially, never concurrently.**
`bundestag_speeches` (DIP) and `openparliament_tv` (op) share cross-source dedup
(op supersedes its DIP twin; DIP has a resurrection guard) that is corrupted if
the two interleave. Pass them as one ordered `CONNECTOR_ID` so non-concurrency is
structural:

```bash
docker compose --profile ingestion run --rm \
  -e CONNECTOR_ID=bundestag_speeches,openparliament_tv ingestion --batch-size 25
```

## Intended shape (for the Terraform workstream)

- **One Cloud Run Job + Cloud Scheduler trigger per connector**, in
  `europe-west1` / `europe-west3` (GDPR Art. 9 EU data-residency constraint).
  Connectors: `abgeordnetenwatch_votes` (one job per legislature ID — federal +
  the 16 Landtage), the speech pair `bundestag_speeches,openparliament_tv` as a
  single **sequential** job (they must never overlap), `manifestos` (infrequent /
  on demand).
- **Single image, `CONNECTOR_ID` selects the connector** (sequential for a
  comma-separated list). The same container serves the FastAPI app (no
  `CONNECTOR_ID`) and every ingestion job; dispatch is in
  `ai-backend/docker-entrypoint.sh`.
- **Task timeout 1h** (`--task-timeout 3600`) — the 15-minute cap is a Firebase
  Scheduled Functions limit, NOT a Cloud Run Jobs limit (Cloud Run allows 24h).
- **Secrets via Secret Manager** (never inline): `OPENAI_API_KEY`,
  `QDRANT_API_KEY`, `DIP_API_KEY`. Auth via Workload Identity — no
  service-account keys.
- **MdB-Stammdaten is fetched at run time** by the speech connectors (the
  speaker→party master file): transient failures are retried, and an
  unavailable file fails the job loudly rather than silently attributing
  ministers / the president to "unbekannt". This keeps the roster fresh without
  rebaking the image; the `unbekannt`-share printed each run is the drift signal.
- **Qdrant corpus** is populated by these scheduled jobs (regular incremental)
  plus a one-time snapshot copy (local → dev/prod) for the initial backfill.
  Qdrant is never seeded from CI (large ingested corpus, not version-controlled
  config).
- **Firestore config** is seeded by `firebase/scripts/seed_firestore.py`
  (`SEED_TARGET=real`). A CI workflow to run it on merge via Workload Identity is
  part of this workstream — it needs the same WIF provider + service account +
  GitHub Environments as the ingestion jobs, so it lands here, not before.

> **Never commit API keys, passwords, or service-account JSON to this directory.**

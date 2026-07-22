# infra/ — deployment (planned via Terraform)

## Status: NOT YET IMPLEMENTED

Scheduled ingestion deployment — Cloud Run Jobs + Cloud Scheduler in an EU
region — is a **dedicated future workstream, provisioned with Terraform**. It is
intentionally not part of the current branch: an earlier hand-authored
`cloud_run_jobs.sh` was removed in favour of doing this properly (declarative,
reviewable, drift-free) alongside the CI / Workload Identity work.

Until then, ingestion runs **locally** via the Makefile targets (`make
run-abgeordnetenwatch-votes`, `make run-speeches`, …), which invoke the same
`src.ingestion.run` entrypoint against the local Qdrant container.

## Intended shape (for the Terraform workstream)

- **One Cloud Run Job + Cloud Scheduler trigger per connector**, in
  `europe-west1` / `europe-west3` (GDPR Art. 9 EU data-residency constraint).
  Connectors: `abgeordnetenwatch_votes` (one job per legislature ID — federal +
  the 16 Landtage), `bundestag_speeches` (DIP, frequent), `openparliament_tv`
  (run so it dedupes against the DIP twins it supersedes), `manifestos`
  (infrequent / on demand).
- **Single image, `CONNECTOR_ID` selects the connector.** The same container
  serves the FastAPI app (no `CONNECTOR_ID`) and every ingestion job (job spec
  sets `CONNECTOR_ID`); dispatch is in `ai-backend/docker-entrypoint.sh`.
- **Task timeout 1h** (`--task-timeout 3600`) — the 15-minute cap is a Firebase
  Scheduled Functions limit, NOT a Cloud Run Jobs limit (Cloud Run allows 24h).
- **Secrets via Secret Manager** (never inline): `OPENAI_API_KEY`,
  `QDRANT_API_KEY`, `DIP_API_KEY`. Auth via Workload Identity — no
  service-account keys.
- **Speeches need `MDB_STAMMDATEN.XML` baked into the image** (gitignored ~15 MB
  master-data file) — without it, speaker→party resolution for empty-`<fraktion>`
  speakers (ministers / president) silently degrades.
- **Qdrant corpus** is populated by these scheduled jobs (regular incremental)
  plus a one-time snapshot copy (local → dev/prod) for the initial backfill.
  Qdrant is never seeded from CI (large ingested corpus, not version-controlled
  config); Firestore config is seeded separately via the
  `Seed Firestore (config)` workflow.

> **Never commit API keys, passwords, or service-account JSON to this directory.**

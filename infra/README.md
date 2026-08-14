# wahl-chat infrastructure (Terraform)

App-serving GCP infrastructure as code. Manages the **Cloud Run services, their env vars, and
their secrets** (plus Artifact Registry and API enablement) and the **scheduled data-ingestion
Cloud Run Jobs with their Cloud Scheduler triggers**, for two environments that are
**separate GCP projects**:

| Env  | Project        | Region        | State bucket             |
|------|----------------|---------------|--------------------------|
| dev  | `wahl-chat-dev`| `europe-west1`| `gs://wahl-chat-dev-tfstate` |
| prod | `wahl-chat`    | `europe-west1`| `gs://wahl-chat-tfstate`     |

Out of scope (owned elsewhere): Firestore rules/indexes, Storage rules, and Cloud Functions
stay with the **Firebase CLI**; the web frontend is on **Vercel**. BigQuery / Pub/Sub are
Firestore-export / eventarc byproducts and are not managed here.

## Layout

```text
infra/
  modules/app/             one reusable module, one file per concern
  modules/ingestion_jobs/  pure composition (no resources): tfvars → complete jobs map
  envs/dev/                thin root: provider + GCS backend + terraform.tfvars → modules
  envs/prod/               same, for the prod project
```

Each env root has its own remote state, so an apply targets exactly one project — prod
cannot be touched from the dev directory, no flag pairing to get wrong. The roots contain
**zero logic** and are file-identical apart from `backend.tf` and `terraform.tfvars`
(verify with `diff envs/dev/main.tf envs/prod/main.tf`); everything envs share lives in
the modules, so dev mirrors prod by construction and only values differ.

## The two rules that keep secrets out of the repo

1. **Two kinds of env vars.** Non-secret config → plain `value =` in the committed
   `terraform.tfvars` (`services[*].env`), reviewable in a diff. Secrets →
   `services[*].secret_env` (env var name → Secret Manager secret id), rendered as a
   `secret_key_ref`. **A secret value never appears in HCL, tfvars, or state.**
2. **Terraform never holds a secret value.** It manages the secret *container* and a
   per-secret accessor grant. For a new secret, seed a bootstrap version (`bootstrap_secret_ids`)
   or add the value out of band:
   ```sh
   echo -n "<value>" | gcloud secrets versions add <secret-id> --project=<project> --data-file=-
   ```
   Cloud Run resolves `version = "latest"`, so rotating a credential is add-version + redeploy —
   no Terraform run.

Terraform and the existing Cloud Build / `gcloud run deploy` **split ownership**: CI owns the
image tag (`ignore_changes = [..image..]`), Terraform owns everything else.

## First-time setup (per env)

1. **Create the state bucket by hand** (Terraform can't bootstrap the bucket holding its own
   state). dev shown; prod uses `wahl-chat-tfstate` / project `wahl-chat`:
   ```sh
   gcloud storage buckets create gs://wahl-chat-dev-tfstate \
     --project=wahl-chat-dev --location=europe-west1 --uniform-bucket-level-access
   gsutil versioning set on gs://wahl-chat-dev-tfstate
   ```
2. `gcloud auth application-default login` (Terraform runs as your ADC identity — this is
   separate from `gcloud auth login`).
3. `cd envs/dev && terraform init`.

## Bringing existing resources under management

The GCP resources already exist, so `terraform import` them rather than creating duplicates,
then iterate the config until `terraform plan` shows **0 to destroy**. Cloud Run services,
secrets and the Artifact Registry repo carry `deletion_protection` / `prevent_destroy`. Import
addresses look like:

```sh
terraform import 'module.app.google_cloud_run_v2_service.svc["wahl-chat-app"]' \
  projects/wahl-chat-dev/locations/europe-west1/services/wahl-chat-app
terraform import 'module.app.google_secret_manager_secret.s["vertex-sa-json"]' \
  projects/wahl-chat-dev/secrets/vertex-sa-json
```

Before `terraform apply`, make sure every secret referenced in `secret_env` has a version in
Secret Manager — a revision that resolves `latest` with no version fails to start.

## Adding or changing a secret

1. Add `SOME_KEY = "some-secret-id"` under the service's `secret_env` in its `terraform.tfvars`.
2. Ensure `some-secret-id` exists with a value (`gcloud secrets versions add …`, or list it in
   `bootstrap_secret_ids` for a sentinel).
3. `terraform apply` — the new revision reads it via `secret_key_ref`.

## Ingestion jobs (Cloud Run Jobs + Cloud Scheduler)

One image serves both roles: `ai-backend/docker-entrypoint.sh` dispatches on `CONNECTOR_ID` —
unset boots the FastAPI app, set runs `python -m src.ingestion.run` for that connector (after an
idempotent Qdrant-collection bootstrap). So a job spec only sets `CONNECTOR_ID` in `env` plus
runner flags in `args` (`--batch-size`, `--time-budget` seconds). Runs are batch-windowed and
resume from a Qdrant-derived cursor: short scheduled executions that continue where they left
off are the design — never raise timeouts to "finish" a backfill.

Job specifics worth knowing (full rationale in `envs/dev/terraform.tfvars` comments):

- `abgeordnetenwatch_votes` needs an explicit `AW_LEGISLATURE_ID` per process, so the env roots
  generate **one job per legislature id** from `aw_daily_legislature_ids` (Bundestag, daily) and
  `aw_weekly_legislature_ids` (Landtage, weekly, staggered). Keep both lists in sync with
  `legislature_config.py`.
- The speech pair runs as ONE sequential job (`CONNECTOR_ID = "bundestag_speeches,openparliament_tv"`)
  — their must-never-overlap invariant is structural, do not split them into two schedules.
- Deployed jobs set `ELECTION_FIXTURES_SOURCE=firestore` and (uploads only)
  `MANIFESTO_UPLOADS_SOURCE=bucket`, because neither the Firestore fixtures nor the uploads
  manifest ship in the image (Docker build context is `ai-backend/`).
- **Image ownership matches the services**: Terraform creates jobs with a placeholder image and
  ignores image changes; the deploy pipeline must `gcloud run jobs update <job> --image=…`
  alongside the service deploy. Until the first CI-driven image update, a job execution runs the
  placeholder and does nothing.
- Prod schedules start `paused = true`; unpause only after the prod corpus is seeded and a manual
  `gcloud run jobs execute <job> --wait` run has been verified per job.

## Applying with editor-only credentials

The basic Editor role cannot create IAM bindings (`*.setIamPolicy`). `manage_iam = false` (set in
both tfvars right now) defers exactly the two binding types — per-secret accessor grants and the
scheduler SA's `run.invoker` on each job — so an editor can apply everything else. The grants are
applied later by an owner or the planned Terraform runner SA flipping `manage_iam = true`.
Until then the runtime/scheduler identities work only if they hold project-level editor (true for
the default compute SA today) — treat that as the bootstrap crutch it is, not the end state.

Migrating a service's plaintext env keys to secret refs without a sentinel-value window:

```sh
terraform apply -target='module.app.google_secret_manager_secret.s'  # containers only
echo -n "<value>" | gcloud secrets versions add <secret-id> --project=<project> --data-file=-  # per secret
terraform apply   # flips the service revisions to secret_key_ref, resolving real values
```

## Constraint: Vertex uses a static service-account secret

`VERTEX_SA_JSON` authenticates via the static `vertex-sa-json` secret rather than ADC /
workload identity, because the target Vertex project does not permit our identities to use ADC.
Keep it as a normal Secret Manager secret; do not convert it to a role-based identity.

## Not tracked here

Environment-specific operator runbooks and one-time migration/import scripts are kept out of
this repo. `terraform.tfvars` holds only non-secret configuration.

# Terraform Migration — wahl-chat (bulk-export from GCP)

Step-by-step runbook for exporting existing GCP infrastructure into Terraform using the
`gcloud beta resource-config` bulk-export tooling (Gemini Cloud Assist tutorial). Execute the
commands manually, in order. Notes and repo-specific values are filled in for you.

## Context

- **Goal:** capture the *existing* GCP infra as `.tf` files + import scripts (brownfield import),
  not author IaC from scratch.
- **Repo state today:** no Terraform, no `terraform/`/`infra/`, no CI/CD. GCP is managed via the
  Firebase CLI + gcloud ADC.
- **Targets:**
  - Dev project: **`wahl-chat-dev`** (region `europe-west1`)
  - Prod project: **`wahl-chat`** (region `us-east1`)
  - Org: **`wahl.chat`**, Org ID **`395224031276`**
- **Frontend (Vercel) is out of scope** — it's not a GCP resource and won't appear in the export.
- **Tooling present:** Google Cloud SDK 561.0.0 (`gcloud`, `gsutil`) confirmed installed.
- Commands are **Beta** — expect gaps (some resource types unsupported) and generated code that
  needs manual cleanup.

## Pre-flight

- Run from the repo root: `/Users/robinfrasch/personal_projects/wahl_chat/wahl-chat-app`
  (exports land in `./terraform-export/`).
- Auth: `gcloud auth login` (user) and `gcloud auth application-default login` (ADC). The repo
  `Makefile` `auth` target already does ADC login + sets project to `wahl-chat-dev`.
- **Permissions needed:** `roles/cloudasset.viewer` + `roles/viewer` at **both project and org**
  level (org export needs org-level grants). Confirm before the org step or it will fail.
- **Do the dev project first**, verify it, then prod, then org.

---

## Step 1 — Prerequisites (one-time)

```bash
# Install the config-connector component
gcloud components install config-connector

# Enable the Cloud Asset API on each target project (run once per project)
gcloud services enable cloudasset.googleapis.com --project=wahl-chat-dev
gcloud services enable cloudasset.googleapis.com --project=wahl-chat
```

> The tutorial enables the API on the "active" project only. Enable it explicitly on **both**
> projects (commands above) so the prod export doesn't fail later.

---

## Step 2 — Export infrastructure to Terraform

The `--resource-format=terraform` flag is essential (otherwise you get Kubernetes KRM, not `.tf`).

```bash
# Dev project
gcloud beta resource-config bulk-export \
  --project=wahl-chat-dev \
  --resource-format=terraform \
  --path=./terraform-export/dev

# Prod project (Project ID: wahl-chat)
gcloud beta resource-config bulk-export \
  --project=wahl-chat \
  --resource-format=terraform \
  --path=./terraform-export/prod

# Organization (Org ID: 395224031276)
gcloud beta resource-config bulk-export \
  --organization=395224031276 \
  --resource-format=terraform \
  --path=./terraform-export/org
```

> **Large org exports:** if prompted, add `--storage-path=gs://<BUCKET_NAME>` to hold the temporary
> Asset Inventory data. Create the bucket first (see below), then re-run the export with the flag.

**Optional — create a temp bucket for the org export (only if prompted for `--storage-path`):**

```bash
# Create a versioned temp bucket for the Asset Inventory export data.
# Bucket names are global — change if taken.
gsutil mb -p wahl-chat -l europe-west1 gs://wahl-chat-tf-export-tmp

# Then re-run the org export pointing at it:
gcloud beta resource-config bulk-export \
  --organization=395224031276 \
  --resource-format=terraform \
  --path=./terraform-export/org \
  --storage-path=gs://wahl-chat-tf-export-tmp

# Clean up the temp bucket once the export succeeds:
gsutil rm -r gs://wahl-chat-tf-export-tmp
```

> Notes: `-p wahl-chat` bills the bucket to the prod project (any project you own works — pick one).
> `-l europe-west1` sets the location. The bucket only holds transient export data, so deleting it
> afterward is safe.

After each export, sanity-check that `.tf` files were produced:

```bash
find ./terraform-export/dev -name '*.tf' | head
```

---

## Step 3 — Generate import scripts

Links the exported `.tf` resources to real cloud resources (so `terraform import` populates state
instead of trying to recreate things).

```bash
# Dev
gcloud beta resource-config terraform generate-import ./terraform-export/dev \
  --output-script-file=import_dev.sh \
  --output-module-file=modules_dev.tf

# Prod
gcloud beta resource-config terraform generate-import ./terraform-export/prod \
  --output-script-file=import_prod.sh \
  --output-module-file=modules_prod.tf

# Org
gcloud beta resource-config terraform generate-import ./terraform-export/org \
  --output-script-file=import_org.sh \
  --output-module-file=modules_org.tf
```

Review before running the scripts:

```bash
less import_dev.sh   # scan the terraform import commands it will run
```

> `import_*.sh` runs `terraform import` per resource against local state. Start with **dev**.

### Step 3a — Per-environment root structure (IMPORTANT)

`gcloud generate-import` writes all three `modules_*.tf` files with their own `provider "google"`
block into the **same directory (repo root)**. Terraform reads a whole directory at once, so running
`terraform init` there fails with **"Duplicate provider configuration"**. Each export is really its
own Terraform root and needs its own directory + own state.

This repo is set up as:

```text
terraform/
  dev/   main.tf  import.sh   # provider project = wahl-chat-dev
  prod/  main.tf  import.sh   # provider project = wahl-chat
  org/   main.tf  import.sh   # provider project = wahl-chat
terraform-export/            # raw exported resource modules (referenced via ../../ from each root)
```

Each `main.tf` is the generated module file with (a) module `source` paths rewritten from
`./terraform-export/...` to `../../terraform-export/...`, and (b) the `provider` project corrected
(the generator wrote `wahl-chat-dev` into all three — prod/org were fixed to `wahl-chat`).

> If you re-run the export and regenerate these files, redo those two rewrites, or run
> `terraform init`/import from three separate directories some other way. Do **not** init all three
> module files together in one directory.

---

## Step 4 — Initialize & verify (dev first)

Run from inside each per-environment root — each keeps its own `.terraform/` and state:

```bash
cd terraform/dev
terraform init
bash import.sh 2>&1 | tee import.log   # tee avoids clogging the terminal; log is reviewable
terraform plan                          # GOAL: "No changes"/trivial diffs = state matches reality
cd ../..
```

- A clean `terraform plan` (no destroys/recreates) means the import captured the existing infra.
- Any resource showing as "to be created" was likely **not imported** (Beta gap) — note it for
  manual import or acceptance.
- Repeat for `prod` then `org`: `cd terraform/prod` / `cd terraform/org`, same three commands.
  No file shuffling needed — each root is independent.

---

## Repo hygiene (before committing anything)

**This repository is PUBLIC.** The `.gitignore` now ignores the entire export output and generated
import artifacts, because bulk-export `.tf` files can embed secrets, IAM policies, and a full map of
the GCP attack surface:

```gitignore
# Terraform
**/.terraform/
*.tfstate
*.tfstate.*
crash.log
*.tfvars
terraform-export/
import_*.sh
modules_*.tf
```

- **Nothing from the export is committed by default.** Review and sanitize each file manually before
  un-ignoring anything specific (e.g. a cleaned-up module you're confident holds no secrets).
- **Never commit** `*.tfstate` (contains secrets) or the local `ai-backend/*firebase-adminsdk*.json`
  service-account keys (already git-ignored).
- If you want the sanitized IaC version-controlled, consider a **separate private repo** for the
  Terraform config rather than this public one.

## Important considerations (from the tutorial)

- **Beta status:** not every resource type is supported — expect to manually add/clean up some.
- **Firebase-CLI overlap:** Firestore rules/indexes, Storage rules, and Cloud Functions currently
  deploy via `firebase deploy`. The export may pull in the underlying GCP resources (Firestore DB,
  buckets, functions). Decide whether Terraform should *own* them or whether you keep deploying
  those via Firebase CLI — **don't run `terraform apply` on imported Firebase-managed resources
  until you've decided**, to avoid the two tools fighting.
- **Permissions:** need Cloud Asset Viewer + Viewer at org and project level.

## Verification checklist

- [ ] `gcloud components list | grep config-connector` shows Installed
- [ ] Cloud Asset API enabled on `wahl-chat-dev` and `wahl-chat`
- [ ] `terraform-export/dev`, `/prod`, `/org` each contain `.tf` files
- [ ] `import_*.sh` reviewed before execution
- [ ] `terraform plan` in dev shows **no destructive changes**
- [ ] `.gitignore` updated; no `*.tfstate` staged

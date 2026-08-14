variable "project_id" {
  description = "GCP project ID (string form, not numeric)."
  type        = string

  validation {
    condition     = !strcontains(var.project_id, "FILL_IN")
    error_message = "project_id must be the real GCP project ID — no FILL_IN placeholder."
  }
}

variable "region" {
  description = "Primary GCP region for every resource that has a location."
  type        = string
  default     = "europe-west1"
}

variable "enable_apis" {
  description = "Whether this module manages google_project_service enablement. Turn off if the runner lacks serviceusage admin and the APIs are already on."
  type        = bool
  default     = true
}

# ── Cloud Run services ──────────────────────────────────────────────────────
# Keyed by service name. `env` holds NON-SECRET config only (it lands in committed
# tfvars and in state — keep it reviewable). `secret_env` maps an env var name to a
# Secret Manager secret id; Cloud Run resolves it from `latest` at deploy time, so the
# value never appears in HCL, tfvars, or state.
variable "services" {
  description = "Cloud Run services to manage, keyed by service name."
  type = map(object({
    service_account      = string
    image                = optional(string, "us-docker.pkg.dev/cloudrun/container/hello")
    cpu                  = optional(string, "1")
    memory               = optional(string, "512Mi")
    min_instances        = optional(number, 0)
    max_instances        = optional(number, 100)
    concurrency          = optional(number, 80)
    timeout_seconds      = optional(number, 300)
    startup_cpu_boost    = optional(bool, true)
    ingress              = optional(string, "INGRESS_TRAFFIC_ALL")
    invoker_iam_disabled = optional(bool, true)
    health_check_path    = optional(string) # httpGet liveness path, or null for a TCP startup probe only
    env                  = optional(map(string), {})
    secret_env           = optional(map(string), {})
  }))
  default = {}
}

# Secret ids that DO NOT yet exist and should get a sentinel bootstrap version created
# by Terraform (the example's four-block pattern). Existing secrets are imported and
# left alone — do NOT list them here, or Terraform would add a sentinel version and move
# the `latest` alias onto it. Real values are added out of band with
#   echo -n "<value>" | gcloud secrets versions add <id> --data-file=-
variable "bootstrap_secret_ids" {
  description = "Secret ids Terraform should seed with a sentinel bootstrap version (brand-new secrets only)."
  type        = set(string)
  default     = []
}

# ── Cloud Run ingestion jobs ────────────────────────────────────────────────
# Keyed by job name; same env/secret_env contract as var.services. The image's
# entrypoint dispatches on CONNECTOR_ID (ai-backend/docker-entrypoint.sh): set it in
# `env` and the container runs `python -m src.ingestion.run`; `args` are forwarded to
# the runner (e.g. --batch-size, --time-budget SECONDS). A non-null `schedule` (cron)
# creates a Cloud Scheduler trigger that executes the job.
#
# Entries are composed with the ingestion_* variables below (tfvars is literal-only,
# so the shared plumbing is merged here, once — see local.jobs in cloud_run_ingestion.tf,
# where local.job_base documents every attribute and its fallback). Loosely typed on
# purpose: a strict optional() schema would materialize its defaults BEFORE that merge
# and silently override ingestion_job_defaults (e.g. a paused=true default would lose
# to the type-level false).
variable "jobs" {
  description = "Cloud Run jobs to manage, keyed by job name; composed with ingestion_job_defaults/env_common/secret_env_common."
  type        = any
  default     = {}
}

variable "ingestion_job_defaults" {
  description = "Shared job plumbing merged into every job: runtime SA, resources, runner args, paused. service_account must come from here or the job entry."
  type        = any
  default     = {}
}

variable "ingestion_env_common" {
  description = "Env vars merged into every job's env (store + embedding config)."
  type        = map(string)
  default     = {}
}

variable "ingestion_secret_env_common" {
  description = "Secret refs merged into every job's secret_env (store + embedding credentials)."
  type        = map(string)
  default     = {}
}

# The basic Editor role cannot create IAM bindings (no *.setIamPolicy), which blocks
# google_secret_manager_secret_iam_member and the scheduler's job-invoker grant. Setting
# this false lets an editor-only identity apply everything else; the grants land when the
# Terraform runner SA (or an owner) applies with true. Only flip it while bootstrapping —
# false in normal operation would DESTROY previously-applied grants.
variable "manage_iam" {
  description = "Whether this module manages IAM bindings (secret accessors, scheduler invoker)."
  type        = bool
  default     = true
}

variable "artifact_registry_repo_id" {
  description = "Artifact Registry Docker repository id CI builds/pushes into."
  type        = string
  default     = "cloud-run-source-deploy"
}

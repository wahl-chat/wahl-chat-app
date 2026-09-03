# ═══════════════════════════════════════════════════════════════════════════════
# CLOUD RUN JOBS — scheduled data-ingestion connectors
#
# Jobs run the dedicated ingestion image (see ingestion/docker-entrypoint.sh —
# own image since the ingestion package split; no chat-service code): a job sets
# CONNECTOR_ID and the entrypoint runs `python -m ingestion.run` after an
# idempotent collection bootstrap; container `args` are forwarded to the runner.
# Runs are batch-windowed and time-budgeted, resuming from a Qdrant-derived
# cursor — an execution that runs out of budget simply continues next run, so
# short scheduled executions are the design, not a limitation.
#
# Same CI split as services: CI owns the image tag (`gcloud run jobs update
# --image`, ignore_changes here), Terraform owns everything else.
# ═══════════════════════════════════════════════════════════════════════════════

locals {
  # Every job attribute and its fallback. Overridden by ingestion_job_defaults,
  # then by the job entry itself (which must supply service_account if the
  # defaults don't). AW vote jobs carry no legislature ids anywhere in infra:
  # they shard at runtime via AW_LEGISLATURE_SET + CLOUD_RUN_TASK_INDEX
  # (resolve_aw_legislature_shard in ingestion/src/ingestion/run.py), so newly
  # configured legislature periods are covered without an infra change.
  job_base = {
    image           = "us-docker.pkg.dev/cloudrun/container/hello"
    cpu             = "1"
    memory          = "1Gi"
    timeout_seconds = 900 # per-TASK cap; pair with a --time-budget arg below it
    max_retries     = 1   # runs are cursor-resumable, so retries are cheap but rarely needed
    task_count      = 1   # sharded jobs: over-provision; spare tasks exit 0
    parallelism     = null
    args            = []
    schedule        = null # cron, or null for manually-executed only
    time_zone       = "Europe/Berlin"
    paused          = false
  }

  jobs = {
    for name, job in var.jobs :
    name => merge(local.job_base, var.ingestion_job_defaults, job, {
      env        = merge(var.ingestion_env_common, try(job.env, {}))
      secret_env = merge(var.ingestion_secret_env_common, try(job.secret_env, {}))
    })
  }

  scheduled_jobs = { for name, job in local.jobs : name => job if job.schedule != null }
}

resource "google_cloud_run_v2_job" "job" {
  for_each = local.jobs

  project  = var.project_id
  name     = each.key
  location = var.region

  # Jobs hold no state or traffic — safe to recreate, unlike the services.
  deletion_protection = false

  template {
    task_count  = each.value.task_count
    parallelism = each.value.parallelism

    template {
      service_account = each.value.service_account
      timeout         = "${each.value.timeout_seconds}s"
      max_retries     = each.value.max_retries

      containers {
        image = each.value.image
        args  = each.value.args

        resources {
          limits = {
            cpu    = each.value.cpu
            memory = each.value.memory
          }
        }

        # ── Plain env vars (non-secret, reviewable) ───────────────────────────
        dynamic "env" {
          for_each = each.value.env
          content {
            name  = env.key
            value = env.value
          }
        }

        # ── Secret env vars (resolved from Secret Manager at execution time) ──
        dynamic "env" {
          for_each = each.value.secret_env
          content {
            name = env.key
            value_source {
              secret_key_ref {
                secret  = env.value
                version = "latest"
              }
            }
          }
        }
      }
    }
  }

  lifecycle {
    # image: owned by the CI deploy step, same split as the services.
    ignore_changes = [
      template[0].template[0].containers[0].image,
      client,
      client_version,
      launch_stage,
      labels,
      template[0].labels,
      template[0].annotations,
    ]
  }

  depends_on = [
    google_project_service.enabled,
    google_secret_manager_secret_iam_member.accessor,
    google_secret_manager_secret_version.bootstrap,
  ]
}

# ── Scheduling ────────────────────────────────────────────────────────────────
# Cloud Scheduler POSTs to the Cloud Run Admin API's :run endpoint as a dedicated
# SA. The :run call is async (returns an operation immediately), so the scheduler
# deadline bounds only the trigger call, never the execution itself.

resource "google_service_account" "job_scheduler" {
  count = length(local.scheduled_jobs) > 0 ? 1 : 0

  project      = var.project_id
  account_id   = "ingestion-scheduler"
  display_name = "Cloud Scheduler -> ingestion jobs"
  description  = "Identity Cloud Scheduler uses to trigger Cloud Run ingestion job executions."
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_invoker" {
  for_each = var.manage_iam ? local.scheduled_jobs : {}

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.job[each.key].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.job_scheduler[0].email}"
}

resource "google_cloud_scheduler_job" "trigger" {
  for_each = local.scheduled_jobs

  project   = var.project_id
  region    = var.region
  name      = "trigger-${each.key}"
  schedule  = each.value.schedule
  time_zone = each.value.time_zone
  paused    = each.value.paused

  attempt_deadline = "180s"

  retry_config {
    retry_count = 1
  }

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${each.key}:run"

    oauth_token {
      service_account_email = google_service_account.job_scheduler[0].email
    }
  }

  depends_on = [google_cloud_run_v2_job.job]
}

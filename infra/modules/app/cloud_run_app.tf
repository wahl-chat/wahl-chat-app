# ═══════════════════════════════════════════════════════════════════════════════
# CLOUD RUN SERVICES  (see infra-example-export/infra/cloud_run.tf)
#
# 1. TERRAFORM AND THE DEPLOY PIPELINE SPLIT OWNERSHIP. CI's `gcloud run deploy` owns the
#    image tag; Terraform owns env vars, secret refs, scaling, resources and the runtime
#    SA. `ignore_changes` on the image (plus the deploy-applied labels/annotations and the
#    client fields) keeps them from reverting each other.
# 2. TWO KINDS OF ENV VARS. Plain `value =` for reviewable config (var.services[*].env);
#    `value_source.secret_key_ref` for secrets (var.services[*].secret_env) — the second
#    kind never appears in HCL, tfvars, or state.
# ═══════════════════════════════════════════════════════════════════════════════

resource "google_cloud_run_v2_service" "svc" {
  for_each = var.services

  project  = var.project_id
  name     = each.key
  location = var.region

  ingress              = each.value.ingress
  invoker_iam_disabled = each.value.invoker_iam_disabled

  # Existing services — imported, not created. Block accidental teardown.
  deletion_protection = true

  scaling {
    min_instance_count = each.value.service_min_instances
  }

  template {
    service_account                  = each.value.service_account
    max_instance_request_concurrency = each.value.concurrency
    timeout                          = "${each.value.timeout_seconds}s"

    scaling {
      min_instance_count = each.value.min_instances
      max_instance_count = each.value.max_instances
    }

    containers {
      image = each.value.image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = each.value.cpu
          memory = each.value.memory
        }
        startup_cpu_boost = each.value.startup_cpu_boost
        # CPU only during requests. Must be explicit once `resources` is set, else the
        # provider sends unset and the service switches to always-allocated CPU.
        cpu_idle = true
      }

      # ── Plain env vars (non-secret, reviewable) ─────────────────────────────
      dynamic "env" {
        for_each = each.value.env
        content {
          name  = env.key
          value = env.value
        }
      }

      # ── Secret env vars (resolved from Secret Manager at deploy time) ────────
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

      dynamic "liveness_probe" {
        for_each = each.value.health_check_path == null ? [] : [each.value.health_check_path]
        content {
          http_get {
            path = liveness_probe.value
          }
        }
      }
    }
  }

  lifecycle {
    # image: owned by the CI deploy step. client/client_version/launch_stage and the
    # gcb-* labels/annotations churn on every deploy — ignore so plans stay clean.
    ignore_changes = [
      template[0].containers[0].image,
      client,
      client_version,
      launch_stage,
      labels,
      template[0].labels,
      template[0].annotations,
      # Set by each `gcloud run deploy` (source build, container name, revision name).
      build_config,
      template[0].containers[0].name,
      template[0].revision,
    ]
  }

  depends_on = [
    google_project_service.enabled,
    # Each referenced secret needs its accessor grant AND a version to exist before
    # Cloud Run resolves `latest`, or a cold apply races and the first revision fails.
    google_secret_manager_secret_iam_member.accessor,
    google_secret_manager_secret_version.bootstrap,
  ]
}

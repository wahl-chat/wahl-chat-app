# ═══════════════════════════════════════════════════════════════════════════════
# SECRETS — the pattern (see infra-example-export/infra/secret_manager.tf)
#
# Terraform manages the secret CONTAINER and a per-secret accessor grant to the runtime
# SA that reads it. It never holds the real value: for brand-new secrets it seeds an
# obvious sentinel version (var.bootstrap_secret_ids) with ignore_changes=[secret_data];
# the real value is added once, out of band, with `gcloud secrets versions add`. Existing
# secrets are imported and their live versions are left untouched.
#
# Cloud Run resolves each secret at `version = "latest"` (see cloud_run_app.tf), so rotation
# is `gcloud secrets versions add` + redeploy — no Terraform run.
# ═══════════════════════════════════════════════════════════════════════════════

locals {
  # Services and jobs share the secret_env contract; union them for secret handling.
  # local.jobs (not var.jobs): the composed map including secret_env_common.
  secret_env_holders = concat(values(var.services), values(local.jobs))

  # Distinct secret ids referenced by any service's or job's secret_env.
  referenced_secret_ids = toset(flatten([
    for holder in local.secret_env_holders : values(holder.secret_env)
  ]))

  # One accessor grant per DISTINCT (secret id, runtime SA) pair — two workloads
  # sharing a secret under the same SA must not produce a duplicate map key.
  secret_accessors = {
    for pair in distinct(flatten([
      for holder in local.secret_env_holders : [
        for secret_id in values(holder.secret_env) : {
          secret_id = secret_id
          sa        = holder.service_account
        }
      ]
    ])) : "${pair.secret_id}::${pair.sa}" => pair
  }
}

resource "google_secret_manager_secret" "s" {
  for_each = local.referenced_secret_ids

  project   = var.project_id
  secret_id = each.key

  replication {
    auto {}
  }

  # Existing secrets are imported; never let a plan tear one down.
  lifecycle {
    prevent_destroy = true
  }

  depends_on = [google_project_service.enabled]
}

# Sentinel bootstrap version for BRAND-NEW secrets only. Gives Cloud Run a `latest` to
# resolve so the first revision starts; the real value replaces it out of band.
resource "google_secret_manager_secret_version" "bootstrap" {
  for_each = var.bootstrap_secret_ids

  secret      = google_secret_manager_secret.s[each.key].id
  secret_data = "BOOTSTRAP-REPLACE-WITH-REAL-${each.key}"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

# Per-secret accessor grant, not a project-wide roles/secretmanager.secretAccessor.
# Each runtime SA can read exactly the secrets its service references.
# Gated on manage_iam: creating these needs setIamPolicy, which Editor lacks (see variables.tf).
resource "google_secret_manager_secret_iam_member" "accessor" {
  for_each = var.manage_iam ? local.secret_accessors : {}

  project   = var.project_id
  secret_id = google_secret_manager_secret.s[each.value.secret_id].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${each.value.sa}"
}

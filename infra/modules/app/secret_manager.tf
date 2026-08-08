# ═══════════════════════════════════════════════════════════════════════════════
# SECRETS — the pattern (see infra-example-export/infra/secret_manager.tf)
#
# Terraform manages the secret CONTAINER and a per-secret accessor grant to the runtime
# SA that reads it. It never holds the real value: for brand-new secrets it seeds an
# obvious sentinel version (var.bootstrap_secret_ids) with ignore_changes=[secret_data];
# the real value is added once, out of band, with `gcloud secrets versions add`. Existing
# secrets are imported and their live versions are left untouched.
#
# Cloud Run resolves each secret at `version = "latest"` (see cloud_run.tf), so rotation
# is `gcloud secrets versions add` + redeploy — no Terraform run.
# ═══════════════════════════════════════════════════════════════════════════════

locals {
  # Distinct secret ids referenced by any service's secret_env.
  referenced_secret_ids = toset(flatten([
    for svc in values(var.services) : values(svc.secret_env)
  ]))

  # One accessor grant per (secret id, runtime SA) pair actually in use.
  secret_accessors = {
    for pair in flatten([
      for svc in values(var.services) : [
        for secret_id in values(svc.secret_env) : {
          secret_id = secret_id
          sa        = svc.service_account
        }
      ]
    ]) : "${pair.secret_id}::${pair.sa}" => pair
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
resource "google_secret_manager_secret_iam_member" "accessor" {
  for_each = local.secret_accessors

  project   = var.project_id
  secret_id = google_secret_manager_secret.s[each.value.secret_id].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${each.value.sa}"
}

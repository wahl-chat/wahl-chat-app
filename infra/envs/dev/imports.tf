# Every secret a service reads is created outside Terraform (with its value) and adopted
# here; the shared VERTEX_SA_JSON / QDRANT_API_KEY come from the ingest-functions deploy or
# the rename steps in ../../README.md. Plan fails until each exists, so an apply can never
# point a revision at a secret without a value. Bootstrap secrets are Terraform-created.
locals {
  adopted_secret_ids = setsubtract(
    setunion(
      toset(flatten([for s in var.services : values(s.secret_env)])),
      toset(["VERTEX_SA_JSON", "QDRANT_API_KEY"]),
    ),
    var.bootstrap_secret_ids,
  )
}

import {
  for_each = local.adopted_secret_ids
  to       = module.app.google_secret_manager_secret.s[each.key]
  id       = "projects/${var.project_id}/secrets/${each.key}"
}

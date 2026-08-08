# Enable exactly the APIs this module uses. disable_on_destroy = false because disabling
# an API on destroy can break unrelated resources in the same project.

locals {
  apis = [
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
    "cloudbuild.googleapis.com",
    "compute.googleapis.com", # Cloud Build's default runtime SA lives here
  ]
}

resource "google_project_service" "enabled" {
  for_each = var.enable_apis ? toset(local.apis) : toset([])

  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

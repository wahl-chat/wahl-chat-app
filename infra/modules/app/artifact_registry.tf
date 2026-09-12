# Docker repo CI builds into: <region>-docker.pkg.dev/<project>/cloud-run-source-deploy/...
# This is the repo Cloud Build's source-deploy already uses for the agent backend.

resource "google_artifact_registry_repository" "cloud_run_source_deploy" {
  project       = var.project_id
  location      = var.region
  repository_id = var.artifact_registry_repo_id
  format        = "DOCKER"
  description   = "Application container images (Cloud Run source deploy)"

  # Existing repo — imported, not created. Guard against accidental teardown.
  lifecycle {
    prevent_destroy = true
  }

  depends_on = [google_project_service.enabled]
}

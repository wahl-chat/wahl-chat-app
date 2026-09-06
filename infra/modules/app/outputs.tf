output "service_uris" {
  description = "Public URL of each managed Cloud Run service, keyed by service name."
  value       = { for name, svc in google_cloud_run_v2_service.svc : name => svc.uri }
}

output "managed_secret_ids" {
  description = "Secret Manager secret ids this module manages."
  value       = sort([for s in google_secret_manager_secret.s : s.secret_id])
}

output "job_names" {
  description = "Managed Cloud Run job names (CI updates their image alongside the services)."
  value       = sort([for j in google_cloud_run_v2_job.job : j.name])
}

output "artifact_registry_repo" {
  description = "Artifact Registry Docker repo path CI pushes into."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.cloud_run_source_deploy.repository_id}"
}

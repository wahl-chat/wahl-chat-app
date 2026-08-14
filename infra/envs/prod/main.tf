terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Composes tfvars values into the full jobs map (per-legislature vote jobs,
# shared plumbing) — pure transformation, no resources.
module "ingestion_jobs" {
  source = "../../modules/ingestion_jobs"

  jobs                      = var.jobs
  job_defaults              = var.ingestion_job_defaults
  env_common                = var.ingestion_env_common
  secret_env_common         = var.ingestion_secret_env_common
  aw_daily_legislature_ids  = var.aw_daily_legislature_ids
  aw_weekly_legislature_ids = var.aw_weekly_legislature_ids
}

module "app" {
  source = "../../modules/app"

  project_id           = var.project_id
  region               = var.region
  services             = var.services
  jobs                 = module.ingestion_jobs.jobs
  bootstrap_secret_ids = var.bootstrap_secret_ids
  manage_iam           = var.manage_iam
}

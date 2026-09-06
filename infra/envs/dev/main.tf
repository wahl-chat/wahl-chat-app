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

module "app" {
  source = "../../modules/app"

  project_id                  = var.project_id
  region                      = var.region
  services                    = var.services
  jobs                        = var.jobs
  ingestion_job_defaults      = var.ingestion_job_defaults
  ingestion_env_common        = var.ingestion_env_common
  ingestion_secret_env_common = var.ingestion_secret_env_common
  bootstrap_secret_ids        = var.bootstrap_secret_ids
  manage_iam                  = var.manage_iam
}

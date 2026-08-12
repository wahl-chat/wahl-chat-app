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

variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "europe-west1"
}

# Typed by the module; `any` here avoids duplicating the object schema.
variable "services" {
  type    = any
  default = {}
}

variable "jobs" {
  type    = any
  default = {}
}

variable "bootstrap_secret_ids" {
  type    = set(string)
  default = []
}

variable "manage_iam" {
  type    = bool
  default = true
}

# ── Ingestion job composition ────────────────────────────────────────────────
# tfvars is literal-only, so the shared plumbing every ingestion job needs
# (runtime SA, runner args, store/embedding env, store secrets) is declared once
# below and merged into each job here. Per-job tfvars entries carry only what is
# specific to that connector.

variable "ingestion_job_defaults" {
  type    = any
  default = {}
}

variable "ingestion_env_common" {
  type    = map(string)
  default = {}
}

variable "ingestion_secret_env_common" {
  type    = map(string)
  default = {}
}

# The abgeordnetenwatch_votes connector requires an explicit AW_LEGISLATURE_ID per
# process, so one job is generated per id. Lists must be kept in sync with
# FEDERAL_LEGISLATURE_IDS / LANDTAG_LEGISLATURE_IDS in
# ai-backend/src/ingestion/connectors/abgeordnetenwatch/legislature_config.py.
variable "aw_daily_legislature_ids" {
  type    = list(number)
  default = []
}

variable "aw_weekly_legislature_ids" {
  type    = list(number)
  default = []
}

locals {
  # Daily vote jobs (Bundestag): staggered minutes in the 04:00 hour.
  aw_daily_jobs = {
    for idx, id in var.aw_daily_legislature_ids :
    "ingest-aw-votes-${id}" => merge(var.ingestion_job_defaults, {
      env = {
        CONNECTOR_ID      = "abgeordnetenwatch_votes"
        AW_LEGISLATURE_ID = tostring(id)
      }
      schedule = format("%d 4 * * *", (idx * 10) % 60)
    })
  }

  # Weekly vote jobs (Landtage): spread across weekdays and early-morning hours
  # so ~33 runs never hit the AW API in one burst.
  aw_weekly_jobs = {
    for idx, id in var.aw_weekly_legislature_ids :
    "ingest-aw-votes-${id}" => merge(var.ingestion_job_defaults, {
      env = {
        CONNECTOR_ID      = "abgeordnetenwatch_votes"
        AW_LEGISLATURE_ID = tostring(id)
      }
      schedule = format("%d %d * * %d", (idx * 13) % 60, 2 + floor(idx / 7), idx % 7)
    })
  }

  # Merge the shared plumbing into every job (explicit tfvars jobs + generated ones).
  jobs = {
    for name, job in merge(var.jobs, local.aw_daily_jobs, local.aw_weekly_jobs) :
    name => merge(var.ingestion_job_defaults, job, {
      env        = merge(var.ingestion_env_common, try(job.env, {}))
      secret_env = merge(var.ingestion_secret_env_common, try(job.secret_env, {}))
    })
  }
}

module "app" {
  source = "../../modules/app"

  project_id           = var.project_id
  region               = var.region
  services             = var.services
  jobs                 = local.jobs
  bootstrap_secret_ids = var.bootstrap_secret_ids
  manage_iam           = var.manage_iam
}

output "service_uris" {
  value = module.app.service_uris
}

output "job_names" {
  value = module.app.job_names
}

output "artifact_registry_repo" {
  value = module.app.artifact_registry_repo
}

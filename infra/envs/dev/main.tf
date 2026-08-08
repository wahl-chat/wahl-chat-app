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

variable "bootstrap_secret_ids" {
  type    = set(string)
  default = []
}

module "app" {
  source = "../../modules/app"

  project_id           = var.project_id
  region               = var.region
  services             = var.services
  bootstrap_secret_ids = var.bootstrap_secret_ids
}

output "service_uris" {
  value = module.app.service_uris
}

output "artifact_registry_repo" {
  value = module.app.artifact_registry_repo
}

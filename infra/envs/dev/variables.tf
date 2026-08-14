# Thin passthrough declarations; values live in terraform.tfvars. Object shapes are
# typed once by the modules (`any` here avoids re-declaring their schemas).

variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "europe-west1"
}

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

variable "aw_daily_legislature_ids" {
  type    = list(number)
  default = []
}

variable "aw_weekly_legislature_ids" {
  type    = list(number)
  default = []
}

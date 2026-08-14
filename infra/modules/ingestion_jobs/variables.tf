# Inputs are deliberately loosely typed (`any`): this module only composes maps; the
# strict object contract is enforced once, by modules/app `var.jobs`, on the output.
# Strict typing here would materialize the app module's optional-attribute defaults
# before the merges below and silently override values from job_defaults (e.g. a
# `paused = true` default would lose to the type-level `false`).

variable "jobs" {
  description = "Explicit per-connector job entries (tfvars `jobs`); each carries only what is specific to that connector."
  type        = any
  default     = {}
}

variable "job_defaults" {
  description = "Shared job plumbing merged into every job: runtime SA, resources, runner args, paused."
  type        = any
  default     = {}
}

variable "env_common" {
  description = "Env vars merged into every job's env (store + embedding config)."
  type        = map(string)
  default     = {}
}

variable "secret_env_common" {
  description = "Secret refs merged into every job's secret_env (store + embedding credentials)."
  type        = map(string)
  default     = {}
}

# The abgeordnetenwatch_votes connector requires an explicit AW_LEGISLATURE_ID per
# process, so one job is generated per id. Keep both lists in sync with
# FEDERAL_LEGISLATURE_IDS / LANDTAG_LEGISLATURE_IDS in
# ai-backend/src/ingestion/connectors/abgeordnetenwatch/legislature_config.py.
variable "aw_daily_legislature_ids" {
  description = "Bundestag legislature ids ingested daily."
  type        = list(number)
  default     = []
}

variable "aw_weekly_legislature_ids" {
  description = "Landtag legislature ids ingested weekly, staggered."
  type        = list(number)
  default     = []
}

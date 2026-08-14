# Pure composition, no resources: turns per-env values (tfvars) into the complete
# jobs map consumed by modules/app. Exists as a module so the logic is written once
# and both env roots stay thin wiring.

locals {
  # One job per Bundestag legislature id: the AW connector reads exactly one
  # AW_LEGISLATURE_ID per process (frozen at import time — see the Makefile's
  # per-subprocess loop), so a single job cannot cover several legislatures.
  # Collapsing these into ONE job needs app-side work first (e.g. mapping
  # CLOUD_RUN_TASK_INDEX -> legislature id); until then it is one job per id.
  # Landtag legislatures are deliberately NOT scheduled — run via
  # `make run-all-landtage-votes` when needed.
  aw_vote_jobs = {
    for idx, id in var.aw_legislature_ids :
    "ingest-aw-votes-${id}" => merge(var.job_defaults, {
      env = {
        CONNECTOR_ID      = "abgeordnetenwatch_votes"
        AW_LEGISLATURE_ID = tostring(id)
      }
      schedule = format("%d 4 * * *", (idx * 10) % 60)
    })
  }

  # Merge the shared plumbing into every job (explicit entries + generated ones).
  jobs = {
    for name, job in merge(var.jobs, local.aw_vote_jobs) :
    name => merge(var.job_defaults, job, {
      env        = merge(var.env_common, try(job.env, {}))
      secret_env = merge(var.secret_env_common, try(job.secret_env, {}))
    })
  }
}

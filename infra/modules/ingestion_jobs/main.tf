# Pure composition, no resources: turns per-env values (tfvars) into the complete
# jobs map consumed by modules/app. Exists as a module so the logic is written once
# and both env roots stay thin wiring.

locals {
  # Daily vote jobs (Bundestag): staggered minutes in the 04:00 hour.
  aw_daily_jobs = {
    for idx, id in var.aw_daily_legislature_ids :
    "ingest-aw-votes-${id}" => merge(var.job_defaults, {
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
    "ingest-aw-votes-${id}" => merge(var.job_defaults, {
      env = {
        CONNECTOR_ID      = "abgeordnetenwatch_votes"
        AW_LEGISLATURE_ID = tostring(id)
      }
      schedule = format("%d %d * * %d", (idx * 13) % 60, 2 + floor(idx / 7), idx % 7)
    })
  }

  # Merge the shared plumbing into every job (explicit entries + generated ones).
  jobs = {
    for name, job in merge(var.jobs, local.aw_daily_jobs, local.aw_weekly_jobs) :
    name => merge(var.job_defaults, job, {
      env        = merge(var.env_common, try(job.env, {}))
      secret_env = merge(var.secret_env_common, try(job.secret_env, {}))
    })
  }
}

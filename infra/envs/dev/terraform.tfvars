# DEV — project wahl-chat-dev. NON-SECRET config only; this file is committed.
# Secret VALUES never live here — secret_env maps env vars to Secret Manager secret ids.
# Ensure each referenced secret has a version before `terraform apply` (see ../../README.md).

project_id = "wahl-chat-dev"
region     = "europe-west1"

# dip-api-key is brand-new (no live plaintext value to migrate — the old DIP key
# expired); the sentinel keeps applies self-contained until a real key is added.
bootstrap_secret_ids = ["dip-api-key"]

# FALSE until the applying identity can create IAM bindings (Editor cannot).
# Flip to true when the Terraform runner SA / an owner applies — see modules/app/variables.tf.
manage_iam = false

services = {
  # ── wahl-chat-app ─────────────────────────────────────────────────────────
  "wahl-chat-app" = {
    service_account = "670868139461-compute@developer.gserviceaccount.com"
    cpu             = "2"
    memory          = "1Gi"
    min_instances   = 1
    max_instances   = 100

    env = {
      API_NAME             = "wahl-chat-api"
      ENV                  = "dev"
      LANGCHAIN_TRACING_V2 = "false"
      LANGCHAIN_ENDPOINT   = "https://api.smith.langchain.com"
      LANGCHAIN_PROJECT    = "wahl-chat-dev"
      QDRANT_URL           = "https://f27dc9d9-98bc-4242-9aa1-8e235ecd611e.europe-west3-0.gcp.cloud.qdrant.io"
      # PROLIFIC_STUDY_ID_MAP / PROLIFIC_COMPLETION_CODES are provided at deploy time, not here.
    }

    secret_env = {
      QDRANT_API_KEY = "qdrant-api-key"
      GOOGLE_API_KEY = "wahl-chat-app-google-api-key"
      OPENAI_API_KEY = "wahl-chat-app-openai-api-key"
    }
  }

  # ── wahl-chat-backend-dev ───────────────────────────────────────────────────
  "wahl-chat-backend-dev" = {
    service_account   = "670868139461-compute@developer.gserviceaccount.com"
    cpu               = "1"
    memory            = "512Mi"
    min_instances     = 0
    max_instances     = 1
    health_check_path = "/healthz"

    env = {
      API_NAME              = "wahl-chat-api"
      ENV                   = "dev"
      LANGCHAIN_TRACING_V2  = "true"
      LANGCHAIN_ENDPOINT    = "https://api.smith.langchain.com"
      LANGCHAIN_PROJECT     = "wahl-chat-dev"
      OPENAI_API_VERSION    = "2024-08-01-preview"
      AZURE_OPENAI_ENDPOINT = "https://dev-wahl-chat-azure-openai.openai.azure.com/"
      QDRANT_URL            = "https://f27dc9d9-98bc-4242-9aa1-8e235ecd611e.europe-west3-0.gcp.cloud.qdrant.io"
      EMBEDDING_PROVIDER    = "gemini"
      EMBEDDING_MODEL       = "gemini-embedding-2"
      EMBEDDING_DIM         = "3072"
      COLLECTION_NAME       = "wahlchat_chunks_dev"
      VERTEX_PROJECT_ID     = "sit-ipai-found-r-wkzt-run-e7gv"
      VERTEX_LOCATION       = "global"
      VERTEX_REQUIRED       = "1"
    }

    secret_env = {
      VERTEX_SA_JSON       = "vertex-sa-json"
      QDRANT_API_KEY       = "qdrant-api-key"
      LANGCHAIN_API_KEY    = "wahl-chat-backend-dev-langchain-api-key"
      OPENAI_API_KEY       = "wahl-chat-backend-dev-openai-api-key"
      PERPLEXITY_API_KEY   = "wahl-chat-backend-dev-perplexity-api-key"
      AZURE_OPENAI_API_KEY = "wahl-chat-backend-dev-azure-openai-api-key"
      GOOGLE_API_KEY       = "wahl-chat-backend-dev-google-api-key"
    }
  }

  # ── wahl-agent-backend ──────────────────────────────────────────────────────
  "wahl-agent-backend" = {
    service_account = "670868139461-compute@developer.gserviceaccount.com"
    cpu             = "1"
    memory          = "512Mi"
    min_instances   = 1
    max_instances   = 3

    env = {
      OPENAI_MODEL    = "openai/gpt-5.2"
      OPENAI_BASE_URL = "https://router.requesty.ai/v1"
    }

    secret_env = {
      OPENAI_API_KEY = "wahl-agent-backend-requesty-key"
    }
  }
}

# ═══════════════════════════════════════════════════════════════════════════════
# INGESTION JOBS (Cloud Run Jobs + Cloud Scheduler)
# One image serves API + jobs; a job only sets CONNECTOR_ID (entrypoint dispatch).
# Runs are cursor-resumable: 15-minute executions that continue where they left off.
# ═══════════════════════════════════════════════════════════════════════════════

# Shared plumbing merged into every job by envs/dev/main.tf.
ingestion_job_defaults = {
  service_account = "670868139461-compute@developer.gserviceaccount.com"
  cpu             = "1"
  memory          = "1Gi"
  timeout_seconds = 900
  # --time-budget below the task timeout so the runner exits gracefully mid-batch
  # instead of being killed; the cursor resumes next run either way.
  args = ["--batch-size", "200", "--time-budget", "780"]
}

ingestion_env_common = {
  ENV                = "dev"
  QDRANT_URL         = "https://f27dc9d9-98bc-4242-9aa1-8e235ecd611e.europe-west3-0.gcp.cloud.qdrant.io"
  COLLECTION_NAME    = "wahlchat_chunks_dev"
  EMBEDDING_PROVIDER = "gemini"
  EMBEDDING_MODEL    = "gemini-embedding-2"
  EMBEDDING_DIM      = "3072"
  VERTEX_PROJECT_ID  = "sit-ipai-found-r-wkzt-run-e7gv"
  VERTEX_LOCATION    = "global"
  VERTEX_REQUIRED    = "1"
}

ingestion_secret_env_common = {
  QDRANT_API_KEY = "qdrant-api-key"
  VERTEX_SA_JSON = "vertex-sa-json"
  OPENAI_API_KEY = "wahl-chat-backend-dev-openai-api-key"
}

# Daily Bundestag vote jobs, one per legislature id (the connector reads exactly one
# AW_LEGISLATURE_ID per process — see modules/ingestion_jobs/main.tf). Keep in sync
# with FEDERAL_LEGISLATURE_IDS (current + prior term) in legislature_config.py.
# Landtag legislatures are NOT scheduled; run `make run-all-landtage-votes` on demand.
# AW_API_KEY is deliberately NOT wired: the connector runs keyless; add a real
# key as a secret only if rate limiting bites (a bootstrap sentinel would be
# sent as a credential and break requests).
aw_legislature_ids = [132, 161]

jobs = {
  # DIP speeches then op.tv video speeches, sequentially in ONE process — their
  # must-never-overlap invariant is structural (run.py comma dispatch).
  "ingest-speeches" = {
    env = {
      CONNECTOR_ID = "bundestag_speeches,openparliament_tv"
    }
    secret_env = {
      DIP_API_KEY = "dip-api-key"
    }
    schedule = "0 3 * * *"
  }

  # AW election-programme catalogue.
  "ingest-manifestos" = {
    env = {
      CONNECTOR_ID             = "manifestos"
      ELECTION_FIXTURES_SOURCE = "firestore" # read contexts/parties from the live DB, not committed fixtures
    }
    schedule = "0 5 * * *"
  }

  # Uploaded party PDFs: reconciles the live GCS bucket against the corpus daily
  # (new objects ingested, vanished objects retired). CI can additionally
  # `gcloud run jobs execute` this right after an upload for instant ingestion.
  "ingest-manifesto-uploads" = {
    env = {
      CONNECTOR_ID             = "manifesto_uploads"
      ELECTION_FIXTURES_SOURCE = "firestore"
      MANIFESTO_UPLOADS_SOURCE = "bucket" # list the live bucket, not the committed manifest
    }
    schedule = "30 5 * * *"
  }
}

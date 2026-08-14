# PROD — project wahl-chat. NON-SECRET config only; this file is committed.
# Secret VALUES never live here — secret_env maps env vars to Secret Manager secret ids.
# Ensure each referenced secret has a version before `terraform apply` (see ../../README.md).

project_id = "wahl-chat"
region     = "europe-west1"

# dip-api-key is brand-new (the old DIP key expired); sentinel until a real key exists.
bootstrap_secret_ids = ["dip-api-key"]

# FALSE until the applying identity can create IAM bindings (Editor cannot).
# Flip to true when the Terraform runner SA / an owner applies — see modules/app/variables.tf.
manage_iam = false

services = {
  # ── wahl-chat-backend ───────────────────────────────────────────────────────
  "wahl-chat-backend" = {
    service_account   = "303509010343-compute@developer.gserviceaccount.com"
    cpu               = "1"
    memory            = "512Mi"
    min_instances     = 1
    max_instances     = 100
    health_check_path = "/healthz"

    env = {
      API_NAME              = "wahl-chat-api"
      ENV                   = "prod"
      LANGCHAIN_TRACING_V2  = "false"
      LANGCHAIN_ENDPOINT    = "https://api.smith.langchain.com"
      LANGCHAIN_PROJECT     = "wahl-chat"
      OPENAI_API_VERSION    = "2024-08-01-preview"
      AZURE_OPENAI_ENDPOINT = "https://prod-wahl-chat-azure-openai.openai.azure.com/"
      QDRANT_URL            = "https://f27dc9d9-98bc-4242-9aa1-8e235ecd611e.europe-west3-0.gcp.cloud.qdrant.io"
      VERTEX_PROJECT_ID     = "sit-ipai-found-r-wkzt-run-e7gv"
      VERTEX_LOCATION       = "global"
      VERTEX_REQUIRED       = "1"
      EMBEDDING_PROVIDER    = "gemini"
      EMBEDDING_MODEL       = "gemini-embedding-2"
      EMBEDDING_DIM         = "3072"
    }

    secret_env = {
      VERTEX_SA_JSON       = "vertex-sa-json"
      QDRANT_API_KEY       = "qdrant-api-key"
      LANGCHAIN_API_KEY    = "wahl-chat-backend-langchain-api-key"
      PERPLEXITY_API_KEY   = "wahl-chat-backend-perplexity-api-key"
      AZURE_OPENAI_API_KEY = "wahl-chat-backend-azure-openai-api-key"
      GOOGLE_API_KEY       = "wahl-chat-backend-google-api-key"
      OPENAI_API_KEY       = "wahl-chat-backend-openai-api-key"
    }
  }

  # ── wahl-agent-backend ──────────────────────────────────────────────────────
  # Runs under the Firebase App Hosting compute SA, not the default compute SA.
  "wahl-agent-backend" = {
    service_account = "firebase-app-hosting-compute@wahl-chat.iam.gserviceaccount.com"
    cpu             = "1"
    memory          = "512Mi"
    min_instances   = 1
    max_instances   = 3

    env = {
      OPENAI_MODEL                       = "gpt-5.2"
      WAHL_CHAT_BACKEND_URL              = "https://wahl-chat-backend-303509010343.europe-west1.run.app"
      WAHL_CHAT_CONTEXT_ID               = "bundestagswahl-2025"
      FIRESTORE_CONVERSATIONS_COLLECTION = "wahl_agent_conversations"
      FIRESTORE_TOPICS_COLLECTION        = "wahl_agent_topics"
    }

    secret_env = {
      OPENAI_API_KEY = "openaiApiKey"
    }
  }
}

# ═══════════════════════════════════════════════════════════════════════════════
# INGESTION JOBS (Cloud Run Jobs + Cloud Scheduler)
# Mirrors dev (see envs/dev/terraform.tfvars for the full rationale per job).
# ALL SCHEDULES START PAUSED (`paused = true` in the defaults): unpause only after
# the prod corpus is seeded and each job has a verified manual `gcloud run jobs
# execute` run — scheduled ingestion into an unseeded prod collection helps nobody.
# ═══════════════════════════════════════════════════════════════════════════════

ingestion_job_defaults = {
  service_account = "303509010343-compute@developer.gserviceaccount.com"
  cpu             = "1"
  memory          = "1Gi"
  timeout_seconds = 900
  args            = ["--batch-size", "200", "--time-budget", "780"]
  paused          = true
}

ingestion_env_common = {
  ENV                = "prod"
  QDRANT_URL         = "https://f27dc9d9-98bc-4242-9aa1-8e235ecd611e.europe-west3-0.gcp.cloud.qdrant.io"
  COLLECTION_NAME    = "wahlchat_chunks_prod"
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
  OPENAI_API_KEY = "wahl-chat-backend-openai-api-key"
}

# Keep in sync with legislature_config.py (see dev tfvars for the full rationale).
aw_legislature_ids = [132, 161]

jobs = {
  "ingest-speeches" = {
    env = {
      CONNECTOR_ID = "bundestag_speeches,openparliament_tv"
    }
    secret_env = {
      DIP_API_KEY = "dip-api-key"
    }
    schedule = "0 3 * * *"
  }

  "ingest-manifestos" = {
    env = {
      CONNECTOR_ID             = "manifestos"
      ELECTION_FIXTURES_SOURCE = "firestore"
    }
    schedule = "0 5 * * *"
  }

  "ingest-manifesto-uploads" = {
    env = {
      CONNECTOR_ID             = "manifesto_uploads"
      ELECTION_FIXTURES_SOURCE = "firestore"
      MANIFESTO_UPLOADS_SOURCE = "bucket"
    }
    schedule = "30 5 * * *"
  }
}

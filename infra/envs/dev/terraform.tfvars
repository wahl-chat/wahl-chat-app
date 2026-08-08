# DEV — project wahl-chat-dev. NON-SECRET config only; this file is committed.
# Secret VALUES never live here — secret_env maps env vars to Secret Manager secret ids.
# Ensure each referenced secret has a version before `terraform apply` (see ../../README.md).

project_id = "wahl-chat-dev"
region     = "europe-west1"

bootstrap_secret_ids = []

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

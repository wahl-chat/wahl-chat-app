# The shared secrets are created outside Terraform (first ingest-functions deploy, or the
# rename steps in ../../README.md) and adopted here. Plan fails until they exist, so an
# apply can never point a revision at a secret without a value.
import {
  to = module.app.google_secret_manager_secret.s["VERTEX_SA_JSON"]
  id = "projects/wahl-chat/secrets/VERTEX_SA_JSON"
}

import {
  to = module.app.google_secret_manager_secret.s["QDRANT_API_KEY"]
  id = "projects/wahl-chat/secrets/QDRANT_API_KEY"
}

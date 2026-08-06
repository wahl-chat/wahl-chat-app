<!--
SPDX-FileCopyrightText: 2026 wahl.chat

SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-->

# AI Backend

Python AI/RAG backend for [wahl.chat](https://wahl.chat/).

Built with FastAPI, sse-starlette (Server-Sent Events), LangChain, and Qdrant. Dependencies are managed with **uv**.

The Pydantic models in `src/ingestion/schemas.py` are the single source of truth for the ingestion data contract (chunk payloads, source items, authority tiers).

## Localization

This project was initially implemented for the German political system.
To adapt it for use in other countries, you will need to adjust the prompts and data schemas to fit the target locale and political context.

## Setup

> Need help? Contact us at [info@wahl.chat](mailto:info@wahl.chat).

### 1. Install dependencies

```bash
uv sync            # all dependencies, including the dev group
uv sync --no-dev   # runtime dependencies only
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Fill in the values. For the LangChain API key (used for tracing on [smith.langchain.com](https://smith.langchain.com)):
1. Set up your own project and API key, or
2. Set `LANGCHAIN_TRACING_V2=false` to deactivate tracing.

### 3. Authenticate with Firebase

The recommended approach for local development is **Google Application Default Credentials (ADC)**:

```bash
gcloud auth application-default login
gcloud config set project wahl-chat-dev
```

Or from the repo root:

```bash
make auth
```

> **Note:** ADC tokens expire periodically (typically daily). When you see a `RefreshError`, simply re-run the command above. The backend will print a clear message when this happens.

**Alternative: Service account JSON file**

For CI/CD or Docker deployments, place a `wahl-chat-dev-firebase-adminsdk.json` file in this directory. Generate it at the [Firebase Console](https://console.firebase.google.com/u/0/project/wahl-chat-dev/settings/serviceaccounts/adminsdk). The backend auto-detects and uses it when present. Note that [Google recommends ADC over service account keys](https://cloud.google.com/docs/authentication#auth-decision-tree) for local development.

> **Security:** never bake a service-account key into the container image. `COPY . /app` would capture it into the image layers permanently, so `.dockerignore` excludes `*-adminsdk-*.json` / `serviceAccount*.json` / `vertex-sa*.json` / ADC files. For deployed environments, supply credentials at runtime via a mounted secret or Workload Identity — not a key copied into the build context.

### Vertex AI (optional): billing Gemini to a separate GCP project

Gemini chat and embeddings can be routed through Vertex AI so the spend lands on a
dedicated GCP project instead of the Google AI Studio `GOOGLE_API_KEY`. This is
**opt-in and fully optional** — with none of the variables below set, the backend
behaves exactly as it always has, which is the default for local development and
CI.

Auth is a service-account key rather than ADC/Workload Identity because the
billing project enforces domain restricted sharing
(`iam.allowedPolicyMemberDomains`): binding this service's runtime identity there
is rejected, so an identity created *inside* the billing project is the only path.

```bash
# ai-backend/.env
VERTEX_SA_JSON_FILE=vertex-sa.json      # gitignored; path is relative to your CWD
VERTEX_PROJECT_ID=<billing-project-id>
VERTEX_LOCATION=global                  # default; see note below
```

In Cloud Run the key arrives as raw JSON from Secret Manager instead
(`--set-secrets="VERTEX_SA_JSON=vertex-sa-json:latest"`), which the code prefers
over the file form. No Dockerfile or entrypoint change is needed.

How it behaves:

- Vertex models are registered **above** their AI Studio twins in
  `RESPONSE_GENERATION_LLMS` / `PRE_AND_POST_PROCESSING_LLMS`, so the existing
  priority-based failover in `src/llms.py` tries Vertex first and falls through to
  the identical AI Studio model on any error.
- `src/llms.py` logs one line at import saying which backend it came up on —
  `Vertex AI enabled for Gemini: project=… location=…`, or a warning that Gemini
  traffic will bill AI Studio. **That line is how you confirm a deploy took**;
  without it the only symptom of a Vertex tier that failed to register is billing
  that never moves.
- `EMBEDDINGS_USE_VERTEX=0` forces embeddings back to AI Studio while chat stays
  on Vertex. It is a manual kill-switch: unlike chat, embeddings have no runtime
  failover, because the client is bound once at module level.
- `EMBEDDING_PROVIDER` stays `gemini` on both backends. It names the *vector
  space*, which is identical across them (verified: same input → bit-identical
  vectors), and it is stamped into the Qdrant embedding-space fingerprint that
  `setup_collection.check_fingerprint` enforces. Changing it would reject the
  existing corpus and force a re-ingest.

#### When credentials are absent vs. broken

These are treated differently on purpose, because only one of them is a mistake.

- **Absent** — no `VERTEX_SA_JSON` / `VERTEX_SA_JSON_FILE` at all. The Vertex tier
  is simply never registered, nothing is logged above DEBUG, and nothing raises.
  This is the CI and local-dev path and it must stay quiet.
- **Broken** — a source *was* supplied but is unusable: blank value, path that does
  not exist, corrupt key, or a key whose project id cannot be resolved. Always
  logs a WARNING naming the specific variable, and for the file form the resolved
  **absolute** path (relative paths are read against the process working
  directory, not the repo root — the usual cause). Vertex is still skipped, so the
  service keeps answering.

Set **`VERTEX_REQUIRED=1`** to escalate the broken case from a warning to a
`VertexConfigError` at import. Do that on deployed revisions: quiet fallback is
the worse failure there, because the service looks healthy while Gemini spend
keeps landing on the project this feature exists to move it off. A failed
revision is noticed in minutes; mis-billing is noticed at the end of the month.

> **Do not set `VERTEX_REQUIRED=1` on a revision whose secret is not wired yet.**
> It escalates *broken* config, not *absent* config — so an unset variable is
> still safe — but a secret that exists and is empty counts as broken and will
> fail the revision's import. Wire the secret, confirm the revision comes up with
> the `Vertex AI enabled` log line, then turn it on.

#### Location

> **`VERTEX_LOCATION=global` is load-bearing.** On the billing project, regional
> endpoints (`europe-west3`/`-west4`, `us-central1`) serve `gemini-2.5-flash`
> alone and 404 on `gemini-embedding-2`, `gemini-2.5-flash-lite` and
> `gemini-3-flash-preview`. Because a 404 falls through to AI Studio silently,
> switching to a regional value would quietly stop most traffic from being billed
> to Vertex rather than producing a visible error. `gemini-2.0-flash` is
> unavailable in every location tested and is deliberately not registered on the
> Vertex tier at all.

## Run

### Locally

```bash
uv run python -m src.app --debug
```

Or run the full stack (web + backend) from the repo root with `make dev`.

### Docker

```bash
# Build
docker build -t wahl-chat:latest .

# Run (dev)
docker run --env-file .env -p 8080:8080 wahl-chat:latest

# Run with gcloud ADC (no service account file needed)
ADC=~/.config/gcloud/application_default_credentials.json && \
docker run --env-file .env \
  -e GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/application_default_credentials.json \
  -e GOOGLE_CLOUD_PROJECT=wahl-chat-dev \
  -v ${ADC}:/tmp/keys/application_default_credentials.json:ro \
  -p 8080:8080 \
  wahl-chat:latest
```

Set `ENV=prod` in `.env` and use `wahl-chat-firebase-adminsdk.json` for production deployments.

## Test

The suite mocks Qdrant/embeddings (see `tests/conftest.py`), so no running backend or live stores are required.

```bash
# Whole suite
uv run pytest

# The SSE chat-endpoint tests
uv run pytest tests/test_chat_sse.py

# A specific test
uv run pytest tests/test_chat_sse.py -k test_get_chat_answer -s
```

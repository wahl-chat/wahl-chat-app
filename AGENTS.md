<!--
SPDX-FileCopyrightText: 2026 wahl.chat

SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-->

# AGENTS.md — wahl.chat

This is the source-of-truth guide for humans and AI assistants working in this
repository: what the system is, how it is built, how to run it, how to treat
data, and how to verify changes. It describes the architecture **as it exists on
this branch**, not a migration plan.

Provider-specific files (e.g. `CLAUDE.md`) are symlinks to this file, created by
`./scripts/setup-agent-docs.sh`. Edit `AGENTS.md` — never a symlink.

## Overview

wahl.chat is a grounded political information chatbot for German elections
(federal, state, and local). It answers questions about parties' positions and
substantiates its answers with citations to primary sources.

The heart of the system is the **data layer and ingestion pipeline**: one
trustworthy, continuously-updated corpus that serves every election from a
single store, ingested once per source and reused across elections. Schema,
contract, pipeline framework, and reference connectors form shared common
ground solid enough that connectors for new sources can be built in parallel
without diverging.

Planned user-facing features (party matcher scoring, profile/onboarding,
proactive chat) are designed-for but not yet built.

## Architecture

Three deployable components plus two data stores:

- **`web/`** — Next.js 15 / React 19 frontend. Chat UI streams tokens and
  citations from the backend over SSE using the Vercel AI SDK v5
  (`@ai-sdk/react` `useChat`).
- **`ai-backend/`** — Python FastAPI service (ASGI, uvicorn). Serves the chat
  RAG pipeline over Server-Sent Events and hosts the ingestion pipeline.
- **`firebase/`** — Firebase config, Cloud Functions, Firestore security rules,
  and seed data. Firestore holds application/session data (election contexts,
  parties, chat sessions); the Firestore emulator is used in local dev.
- **Qdrant** — the single vector store for the corpus (one collection per
  environment).
- **OpenAI + Google Gemini** — OpenAI `text-embedding-3-large` for embeddings;
  Gemini (via `langchain-google-genai`) for answer generation.

### Data flow

```
source APIs / documents
        │  (ingestion connectors: discover → fetch → normalize)
        ▼
   ChunkRecord[]  (Pydantic contract, src/ingestion/schemas.py)
        │  (runner: embed with text-embedding-3-large → upsert)
        ▼
   Qdrant  wahlchat_chunks_{env}   ← single corpus collection
        │  (retrieval: filtered vector search, retrieve.py)
        ▼
   chat_service / chatbot_async  (Gemini generation, grounded + cited)
        │  (SSE, Vercel AI SDK v5 UI-message-stream)
        ▼
   web useChat  →  streamed answer + citations
```

**Ingestion** is a synchronous single-pass pipeline (`src/ingestion/run.py`).
Every connector subclasses `BaseConnector` (`src/ingestion/connector.py`) and
implements three pure data-transform methods:

- `discover(since)` — list upstream external IDs to fetch, filtered by the
  cursor. (Do **not** use a naive `external_id > since` filter — use
  set-difference or a lookback floor so transient failures are re-surfaced. See
  the `discover` docstring.)
- `fetch(external_id)` — retrieve one raw item.
- `normalize(raw)` — transform into a list of validated `ChunkRecord`s.

The runner owns everything else: it derives the cursor (`since`) from Qdrant's
`max(external_id)` for the connector's `source_type` (no separate watermark
store), embeds chunk text, and upserts. Upserts are **idempotent** via
deterministic point IDs (`compute_chunk_id(source_item_id, chunk_index)`), and
change-aware via `content_hash` so upstream corrections re-embed while unchanged
items are cheaply skipped. Connectors that need store-side follow-up override
`post_upsert()`.

Connectors are registered in a closed `{connector_id: factory}` map
(`src/ingestion/registry.py`). Registered IDs:

- `abgeordnetenwatch_votes` — Abgeordnetenwatch vote records (the canonical
  `vote_record` producer; federal + all 16 Landtage).
- `bundestag_speeches` — live incremental Bundestag plenary speeches from the
  DIP API (`source="dip"`).
- `openparliament_tv` — keyless openparliament.tv bulk speeches (`source="op"`);
  coexists with and supersedes DIP twins, deduped on `speech_key`.
- `manifestos` — party manifesto chunks (has its own local CLI in
  `connectors/manifestos/bulk.py`; also runnable via the registry).
- `manifesto_uploads` — party manifesto PDFs supplied to us directly
  (`source="upload"`), for elections Abgeordnetenwatch does not cover. Same
  `party_manifesto` corpus as `manifestos`. An uploaded `wahlprogramm` is retired
  automatically once AW carries the same programme (AW is the citable source); a
  `parteidokument` never is. One policy, two triggers: AW's `post_upsert`
  (`connectors/manifestos/supersede.py`) retires it immediately — the common order,
  since parties send drafts before AW lists the final text — and this connector
  re-decides the same thing per document on every run, which makes it idempotent if
  that hook ever fails. Both read the class from the object path, so neither can
  remove a document the AW copy does not replace.

The **data contract** is the Pydantic model set in `src/ingestion/schemas.py`
(`ChunkRecord` plus the `AuthorityTier` / `SourceType` enums and per-source
`meta` builders `VoteMeta` / `SpeechMeta`). It is the single source of truth for
what a corpus chunk looks like; connectors produce `ChunkRecord`s and the runner
stores them.

### Qdrant collection design

One collection per environment: `wahlchat_chunks_{ENV}` (created by
`src/ingestion/setup_collection.py`). Rationale and invariants:

- **Single collection, payload filtering** — not one collection per election or
  per party. Cross-election shared documents are stored once; queries filter by
  payload. Collection count stays bounded.
- **Multitenancy by `party_id`** — `party_id` is a tenant key
  (`is_tenant=True`), and HNSW is configured `m=0, payload_m=16` (no global
  graph is built, because every query filters by `party_id`).
- **Region** is stored as a scalar `region` keyword on each chunk and matched
  with `MatchAny` against the election's region path at query time — never as a
  queryable array field.
- **Locked vector space** — 3072-dim, COSINE distance. `EMBEDDING_DIM` and
  `EMBEDDING_MODEL` in `setup_collection.py` are the canonical source of truth;
  changing either invalidates index parity. The runner asserts every vector's
  dimension before upsert (`DimensionMismatchError`).

### Chat / SSE transport

The chat endpoint is `POST /api/v1/chat` (`src/routes/chat.py`). It streams
Vercel AI SDK v5 UI-message-stream parts as SSE (`text/event-stream`, header
`x-vercel-ai-ui-message-stream: v1`), which the frontend's `useChat` parses.
SSE is used instead of WebSockets/Socket.IO because WebSockets fail behind some
corporate networks. Other routers: `pro_con`, `voting_behavior`, `misc`, plus a
`/healthz` check.

## Repository layout

| Path | What lives there |
|------|------------------|
| `web/` | Next.js frontend (app router in `web/app/`, shared code in `web/lib/`). Package manager: bun. |
| `ai-backend/` | Python backend. Package manager: uv. |
| `ai-backend/src/app.py` | FastAPI entry point (uvicorn). |
| `ai-backend/src/routes/` | HTTP routers: `chat` (SSE), `pro_con`, `voting_behavior`, `misc`. |
| `ai-backend/src/chat_service.py`, `chatbot_async.py` | RAG chat pipeline + LLM streaming. |
| `ai-backend/src/ingestion/` | Ingestion framework: `connector.py` (base class), `run.py` (runner), `registry.py`, `schemas.py` (data contract), `setup_collection.py`, `retrieve.py`, `ids.py`, `speech_key.py`, `speech_dedup.py`. |
| `ai-backend/src/ingestion/connectors/` | Per-source connectors: `abgeordnetenwatch/`, `bundestag_speeches/`, `openparliament_tv/`, `manifestos/`. Each has `connector.py`, a `client.py`, and `mappers/` that build `ChunkRecord`s. |
| `ai-backend/src/models/` | Pydantic DTOs and domain models for the chat API. |
| `ai-backend/tests/` | pytest suite (Qdrant/embeddings mocked in `conftest.py`). |
| `firebase/` | Firestore rules (`firestore.rules`), Cloud Functions, seed script (`scripts/seed_firestore.py`), rules tests (`tests/`). |
| `infra/` | Scheduled-ingestion deployment — planned Terraform workstream (Cloud Run Jobs + Scheduler); see `infra/README.md`. |
| `scripts/` | Repo-root scripts: `check_gdpr_wall.py` (CI guard), `setup-agent-docs.sh`. |
| `Makefile` | Developer convenience targets (install, stores, dev, test, lint, ingestion runs). |
| `docker-compose.yml` | Local Qdrant service. |

## How to run it

Prerequisites: bun 1.3.x, uv 0.11.x, Docker (with Compose), Firebase CLI, Node
22+. No production credentials are needed for local development — all data
stores run locally.

The `Makefile` at the repo root is the entry point for most workflows.

```bash
# One-time: link CLAUDE.md → AGENTS.md for AI assistants (optional)
./scripts/setup-agent-docs.sh

# Install all dependencies (web via bun, ai-backend via uv)
make install

# Configure env (pre-filled for local mode; add LLM keys for chat)
cp ai-backend/.env.example ai-backend/.env
cp web/.env.example web/.env.local

# Start local stores: Qdrant (Docker) + Firestore emulator (port 8081)
make stores-up

# Seed scrubbed fixtures into the Firestore emulator (guarded — refuses to run
# without FIRESTORE_EMULATOR_HOST, so it can never write to production)
FIRESTORE_EMULATOR_HOST=localhost:8081 make seed-local

# Real Firebase project (ENV=dev by default). Confirm before ENV=prod.
# Optional REVALIDATE_SECRET busts that deployment's Next.js cache afterwards.
make seed
make seed-prod
REVALIDATE_SECRET=... make revalidate

# Dev servers: web on :3000, backend on :8080
make dev            # assumes stores already up
make dev-local      # stores + both servers
make stores-down    # stop stores
```

Run individual services directly if you prefer:

```bash
cd web && bun run dev                       # frontend
cd ai-backend && uv run python -m src.app   # backend (add --debug for verbose logs)
```

### Running ingestion connectors

Before any ingestion, create the collection once (idempotent):

```bash
cd ai-backend && QDRANT_URL=http://localhost:6333 uv run python -m src.ingestion.setup_collection
```

Then run a connector. All connectors go through the same
`python -m src.ingestion.run --connector <id>` entrypoint; the `Makefile` wraps
the common cases (Qdrant URL is wired to local automatically). They require
`make stores-up` first and the relevant API keys in `ai-backend/.env`
(`OPENAI_API_KEY` always, plus `DIP_API_KEY` for speeches, optionally
`AW_API_KEY`).

```bash
make run-abgeordnetenwatch-votes          # federal votes
make run-all-landtage-votes               # loop over all 16 Landtag legislatures
make run-speeches ARGS="--batch-size 25"  # live DIP speeches
make run-manifestos ARGS="--dry-run"      # parse only, zero OpenAI cost
make run-manifesto-uploads ARGS="--check" # validate uploaded-PDF metadata
make speeches-stats                       # read-only Qdrant verification
```

#### Adding a manifesto we received as a file

For elections Abgeordnetenwatch hasn't catalogued (upcoming/communal). The upload
path carries the metadata — election and party must already exist in
`firebase/firestore_data/{env}/contexts.json` (with `region_path` + `level`) and
`parties_{context_id}.json`, since those decide whether a chunk is ever retrievable.

1. Name the file `{document-name}_{YYYY-MM-DD}.pdf`, place at
   `public/{context_id}/{class}/{party_id}/{file}.pdf` under `firebase/storage_data/`,
   where `{class}` is `wahlprogramme` (the programme the party runs on — AW may
   later replace it) or `parteidokumente` (a Grundsatzprogramm or Satzung we hold
   only because the party published no Wahlprogramm — never auto-retired).
2. Add the object path to `ai-backend/data/manifesto_uploads/{env}.txt`.
3. `make upload-manifesto-uploads` (uploads + grants public read).
4. `make run-manifesto-uploads ARGS="--check"`, then drop `ARGS` to ingest.

`--since` (or `MANIFESTO_UPLOADS_SINCE`) floors by election date; documents below it
are neither ingested nor retired. Removing a manifest line retires that document's
chunks on the next run.

De-dup with AW is two-way and party+region+date scoped: an upload is skipped if AW
already has that party's programme; once AW ingests it, its `post_upsert` deletes
the uploaded twin.

Two backend switches, both explicit env vars (no auto-fallback):
`MANIFESTO_UPLOADS_SOURCE=bucket` lists the live bucket instead of the manifest
(what a deployed Job uses — the manifest ships inside the image);
`ELECTION_FIXTURES_SOURCE=firestore` reads the live database instead of the seed
files (also not in the image).

In production the same `src.ingestion.run` code path runs as a Cloud Run Job
with `CONNECTOR_ID` set in the job spec (deployment + scheduling is a planned
Terraform workstream — see `infra/README.md`).
Ingestion must tolerate the 15-minute scheduled-job cap: runs are
batch-windowed and time-budgeted (`--batch-size`, `--time-budget`) and resume
from the Qdrant-derived cursor on the next run.

### Seeding dev/prod

The two stores are seeded by different mechanisms, on purpose:

- **Firestore config** (contexts / parties / proposed_questions) — small and
  version-controlled. Seeded into a real project by running `seed_firestore.py`
  with `SEED_TARGET=real`; the script refuses a real target without an explicit
  project, and refuses prod without `SEED_CONFIRM_PROJECT`. The CI workflow that
  runs this via Workload Identity (no service-account key) on merge lands with the
  deployment workstream (see `infra/README.md`).
- **Qdrant corpus** — large and ingested, not version-controlled. Populated by
  the scheduled Cloud Run ingestion jobs; for the initial backfill, copy a Qdrant
  snapshot from the local/known-good store into the dev/prod store once (Qdrant
  snapshot create → upload → recover). Qdrant is never seeded from CI.

## How to treat data

- **Political opinions are GDPR Art. 9 special-category data.** Handling
  requires explicit consent and EU data residency (`europe-west1` /
  `europe-west3`). A user's political opinions must **never** be embedded into
  the corpus. Ingestion/corpus code must not read the Firestore `users/` path —
  this is enforced in CI by `scripts/check_gdpr_wall.py` (the "GDPR Art. 9
  wall"), which fails the build if ingestion code references `users/`
  collections. Firestore security rules gate chat-message privacy (tested in the
  `firebase-rules` CI job). The explicit Art. 9 consent gate on a user's own
  political answers is **not** on this branch: it returns with the party-matcher
  feature (the first thing that stores those answers), which must ship with a
  real affirmative opt-in — consent cannot be implied from app usage.
- **Local-only stores during this milestone.** Develop against local Qdrant and
  the Firestore emulator; do not point local work at production stores while the
  data design is still settling. The seed script hard-requires
  `FIRESTORE_EMULATOR_HOST`.
- **Corpus rollout gate.** The runtime must not serve corpus-grounded chat
  before the corpus is populated (scheduled ingestion + snapshot backfill are
  deferred — see `infra/README.md`). A deployment opts into enforcement with
  `REQUIRE_CORPUS=true`: the app then refuses to boot if `wahlchat_chunks_{ENV}`
  is missing/empty. Unset locally/in CI/tests, so an empty local store still
  boots.
- **The embedding model and vector store are locked.** Qdrant is the vector
  store; embeddings are OpenAI `text-embedding-3-large` at 3072 dimensions,
  COSINE distance. Do not mix models or dimensions — it breaks index parity.
  Treat `EMBEDDING_DIM` / `EMBEDDING_MODEL` in `setup_collection.py` as
  immutable after the first run.
- **The corpus is source-cited.** Chunks carry `citation_url` / `citation_title`
  and an `authority_tier` (`authoritative` | `factual_record` | `self_reported`
  | `promotional`). Preserve citations end-to-end; answers are grounded in
  retrieved chunks.

## Coding guidelines

- **Language.** Write code, identifiers, and comments in English. Keep
  German-election domain terms (e.g. `Wahlperiode`, `Landtag`, `Drucksache`,
  `Fraktion`, party slugs) as-is — do not translate them.
- **Prefer strong types over loose strings/dicts.** Use enums
  (`AuthorityTier`, `SourceType`) and typed Pydantic models over bare strings;
  use typed `meta` builders (`VoteMeta`, `SpeechMeta`) rather than free-form
  dicts. For Gemini tool declarations use `Literal[...]` rather than Python
  `Enum` (avoids a langchain-google-genai class of bug — see `retrieve.py`).
- **Comment style.** Comments should explain *why* — rationale, non-obvious
  semantics, gotchas, and invariants. Do **not**:
  - restate what the code plainly does;
  - narrate the development process or describe what changed "in this PR" —
    comments should be timeless and read correctly by someone seeing the code
    fresh.
- **Prefer small, well-named functions over walls of comments.** When a long
  function needs block comments to stay navigable (nested loops, multi-stage
  logic), split it into smaller, meaningfully named functions instead — the
  names carry the narration.
- **No internal references, anywhere.** Internal planning/decision/tracking
  identifiers must never appear in the codebase — not in comments, and not in
  runtime strings (error messages, logs, `argparse` help, `Field(description=)`,
  printed output). This covers decision/plan/research IDs (`D-…`, `T-…`, `C…`,
  `G…`, `SC…`, `VEC-…`, `FOUND-…`), phase numbers (`Phase 9`), plan/task refs
  (`plan 01-08`, `Task 2`), doc filenames (`RESEARCH.md`, `PLAN.md`), and
  code-review finding IDs (`HIGH-1`, `MED-02`). Write the reasoning or the
  user-facing message, never the paper trail.
## How to test / verify changes

Local commands (mirror what CI runs):

```bash
# Backend
cd ai-backend
uv run ruff check src/            # lint
uv run mypy src/                  # type-check
uv run pytest                     # full suite (Qdrant/embeddings mocked)
# From repo root:
make test-backend                 # unit/integration (excludes smoke + local-mode)
make test-smoke                   # E2E SSE smoke test (in-process ASGI)
make test-local-mode              # seed-guard test — needs live stores (make stores-up)

# GDPR Art. 9 wall guard (repo root)
python3 scripts/check_gdpr_wall.py

# Frontend
cd web
bun run lint                      # next lint + biome ci
bun run typecheck                 # tsc --noEmit
bun run test                      # bun test
bun run build                     # stop the dev server first — see below
```

`bun run build` and `next dev` share `web/.next`, so building while a dev server
is running corrupts it: pages start failing with
`Cannot find module './vendor-chunks/@firebase.js'`, or render with no stylesheet
at all, which looks like the CSS was deleted. Stop the dev server before
building, and recover with `rm -rf web/.next` before starting it again.

The backend test suite mocks Qdrant and embeddings (`tests/conftest.py`), so no
running services or live API keys are needed. `git` pre-commit hooks are wired
via husky (`.husky/`).

CI (`.github/workflows/ci.yml`) runs four jobs on every push/PR:

- **backend** — GDPR wall guard → `uv sync --locked` → ruff → mypy → pytest
  (excluding the smoke and local-mode tests).
- **frontend** — `bun install --frozen-lockfile` → `bun audit --audit-level=high`
  (supply-chain gate) → lint → tsc → build.
- **firebase-rules** — Firestore security-rules tests against the emulator
  (proves the chat-message privacy rules).
- **smoke-test** — the E2E SSE smoke test, in-process via `httpx.ASGITransport`
  (needs backend + frontend green first).

Verify changes with the relevant test suites — extend them with regression /
integration coverage for what you changed rather than relying on lint output.
Linting, formatting, and type-checking run automatically in the pre-commit
hooks and CI, so they need no explicit step. Run the GDPR wall guard if you
changed ingestion code.

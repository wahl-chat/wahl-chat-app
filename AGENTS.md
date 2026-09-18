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
- **Google Gemini** — `gemini-embedding-2` for embeddings and Gemini (via
  `langchain-google-genai`) for answer generation. The embeddings factory can
  also build an OpenAI client, but no environment runs it; see the locked-model
  note under "How to treat data".

### Data flow

```
source APIs / documents
        │  (ingestion connectors: discover → fetch → normalize)
        ▼
   ChunkRecord[]  (Pydantic contract, src/ingestion/schemas.py)
        │  (runner: embed with gemini-embedding-2 → upsert)
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

Outside the registry (bespoke runner, like the manifesto bulk CLIs):

- `pledgetracker` — evidence timelines for political pledges from the Cambridge
  PledgeTracker research project (EMNLP 2025 demo,
  https://aclanthology.org/2025.emnlp-demos.64/). Not in `CONNECTOR_FACTORIES`:
  pledges have no monotonic cursor and the runner dual-writes Firestore
  (`pledges/{pledge_id}`, the source of truth incl. timelines) + Qdrant (one
  `pledge_record` vector per pledge, timelines never embedded). Runner:
  `connectors/pledgetracker/bulk.py` (see "Running PledgeTracker ingestion").

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
make run-manifestos ARGS="--dry-run"      # parse only, zero embedding cost
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

#### Running PledgeTracker ingestion

The Cambridge queue API is an async job queue in front of a single GPU: one job
at a time, ~3 minutes per pledge, results stored server-side. We own the pledge
list (`ai-backend/data/pledges/*.jsonl`: claim, `pledge_date`, `pledge_author`,
optional `bundesland`/`party_id`/source metadata). Bundesländer map to ISO
3166-2 region codes (`DE-ST`), which must match the context seeds' `region_path`
elements. The runner is incremental: a freshness watermark skips pledges checked
within `--freshness-days` (default 7), interrupted runs resume via the job id
persisted on the Firestore doc, and `--batch-size` (default 3) bounds each
invocation — sized for the 15-minute scheduled-job cap. Pledge identity is
`party_id:claim:region:pledge_date`, so NEVER reword a claim in place — a live
run ends with a reconcile that retires store pledges no longer in the registry
(edited claims, removed rows), scoped to the registry's own regions
(`--skip-reconcile` opts out).

Requires `PLEDGETRACKER_API_KEY` in `ai-backend/.env` (gitignored — never commit
it) and `PLEDGETRACKER_ENABLE_LIVE=true`; without them the runner ingests the
packaged demo fixture offline. `FIRESTORE_EMULATOR_HOST` is mandatory unless
`ENV=prod` (accidental-write guard); pass `--allow-remote` to deliberately
ingest into the deployed dev environment without an emulator. The flag unsets
the emulator host even if `.env` still has it (local mode sets it by default).

```bash
FIRESTORE_EMULATOR_HOST=localhost:8081 make run-pledgetracker ARGS="--dry-run"
FIRESTORE_EMULATOR_HOST=localhost:8081 PLEDGETRACKER_ENABLE_LIVE=true \
  make run-pledgetracker ARGS="--registry data/pledges/sachsen_anhalt_pledges.jsonl --batch-size 2"
# Deployed dev Firestore (wahl-chat-dev), not the emulator:
make run-pledgetracker ARGS="--allow-remote --registry data/pledges/sachsen_anhalt_pledges.jsonl --batch-size 2"
# Backfill short event headlines only (LLM calls, no queue jobs / Qdrant writes):
FIRESTORE_EMULATOR_HOST=localhost:8081 make run-pledgetracker ARGS="--backfill-titles"
```

Data-handling invariants: Cambridge's per-event `Ja`/`Nein` label maps to
`is_relevant_for_tracking` (useful evidence), never a fulfilled/broken verdict —
UI copy says "Ziele", not "Versprechen"; the events' full source text is never
stored (`url`/`title` suffice); the chat-side lookup is best-effort and may
return nothing (the UI then shows no PledgeTracker entry point).

#### The PledgeTracker study (consent, cohorts, questionnaire)

An in-app experiment with the Vlachos group (University of Cambridge): does
PledgeTracker change users' willingness to engage in political debate?

- **Scope**: only `abgeordnetenhauswahl-berlin-2026` and
  `landtagswahl-mecklenburg-vorpommern-2026` — `STUDY_CONTEXT_IDS` in
  `web/lib/pledge-study/study-config.ts`, which also holds the prompt-timing
  constants, the cohort hash, and the questionnaire form id. The shared
  vocabulary (`StudyParticipation`, `StudyCohort`) lives in
  `web/lib/pledge-study/types.ts`: **participation** says whether a user
  consented to the research instruments (`experimental` / `regular`), **cohort**
  says which version of the product they get (`control` / `manipulation`). The
  two are INDEPENDENT: everyone who answers the dialog is assigned an arm,
  declines included, so a `regular` user can be in `manipulation` and see the
  feature. "experimental" therefore never means "sees the feature".
- **Kill switch**: Firestore doc `system_status/pledge_study` `{enabled: true}`.
  Missing doc/field/error = off (the safe default); flipping it is a console
  edit, no deploy. **Off means PledgeTracker is hidden in EVERY context, not
  just the study ones** — the feature is new and only ships inside a study for
  now, so switching the study off must not silently roll the feature out to
  every election. Turning it ON is therefore what NARROWS visibility, to the
  manipulation arm inside a study context. It follows that non-study elections
  need the switch value too, which is why `ChatStudyWrapper` mirrors it into
  the store in every context. The local emulator UI is disabled, so write the doc over
  REST instead, with `-H 'Authorization: Bearer owner'` (plain writes are
  refused by the rules).
  The questionnaire form id is COMMITTED (`STUDY_QUESTIONNAIRE_FORM_ID` in
  `web/lib/pledge-study/study-config.ts`), like every other Fillout form here,
  so a fresh checkout and both deployments work with no env setup;
  `NEXT_PUBLIC_STUDY_QUESTIONNAIRE_URL` only overrides it for a test form.
- **Flow**: fresh chat in a study context → two-stage consent (short ask, then
  the Einverständniserklärung). A „Nein" is permanent per uid, and dismissing
  the dialog (Escape, overlay click, drawer swipe) is recorded as that same
  „Nein" — only an explicit „Ja" enrols, and everyone who was asked leaves a
  record, so the consent denominator is complete. A „Ja" assigns the cohort —
  deterministic hash(uid+salt), p=0.5 — and persists `study_participants/{uid}`
  with `participation`, `cohort` and `assignment_source` (the analysis source
  of truth). NEVER change the salt while the study runs.
  Both answers also record `context_id` and `party_ids` (the parties selected
  when the ask appeared), so non-response can be modelled rather than just
  counted — refusal by election, and by the party the user came to chat with.
  Every answer also records `consent_stage` (`ask` | `consent`) and, on a
  decline, `decline_reason` (`explicit` | `dismissed`): all four refusal paths
  land in the same action, and without these the short ask and the formal
  Einverständniserklärung are one undifferentiated number. Acceptances are
  always `consent_stage: 'consent'`. Rows written before 2026-09-17 have
  neither field — that is what "stage unknown" means in the analysis. Note
  that closing the TAB still leaves no record at all, at either stage.
  BOTH answers also assign and persist a `cohort`, from the same
  `hash(uid+salt)`, so a uid's arm never depends on the answer it gave. Rows
  written before 2026-09-18 have no cohort on the decline side; a returning
  user is never re-asked, so those uids stay arm-less unless backfilled.
  The `?sg=x` ("declined") override is the one decline that stays arm-less on
  purpose — it demonstrates that experience — and the decline action honours
  that absence instead of hashing an arm in.
- **Gate** (`web/lib/pledge-study/gate.ts`): the switch is checked FIRST — off
  or not-yet-known hides PledgeTracker everywhere. With it on, a study context
  admits the `manipulation` arm and nobody else. **THE ARM DECIDES, NOT THE
  CONSENT ANSWER** (changed 2026-09-18): consent governs the research
  instruments, the arm governs which build of the product is served, and
  requiring both left the manipulation arm in single digits. Control sees
  nothing — that is the comparison — and a user who was never asked has no arm
  and sees nothing either. Pre-exposure cannot contaminate anyone: the arm is a
  deterministic `hash(uid+salt)`, identical whenever it is computed, so there is
  no later assignment to spoil. Any other context is the ordinary product and
  shows the feature to everyone. Covered by `gate.test.ts`.
- **Telemetry** (`recordStudyEvent`, written for EVERYONE who answered the
  dialog — both arms and both answers; a user who was never asked has no row
  and is a strict no-op, or the consent denominator would be destroyed):
  append-only `events` on the participant doc — `first_message`, `first_answer_completed`,
  `second_answer_completed`, `pledge_shown` (viewport exposure),
  `pledge_modal_open`/`_close`,
  `prompt_shown`/`prompt_dismissed` (with trigger), `questionnaire_clicked`.
  Counts and firsts are derived from the log at analysis time.
- **Questionnaire prompts** (identical for both cohorts — control symmetry,
  and now genuinely so): `second_answer` fires `SECOND_ANSWER_DELAY_MS` (10s)
  after the PARTICIPANT's second answer completes; `absolute_timer` fires
  `ABSOLUTE_FALLBACK_MS` (90s) after the first completed answer of the chat,
  so a user who never sends a second message is still asked once. Both stand
  down once anything has prompted, so whichever comes first wins and two
  prompts cannot land seconds apart. Max 2 prompts ever, cap survives reloads.
  The answer count is per PARTICIPANT, not per chat: it is seeded from the
  event log at hydration and carried through `newChat`, because `newChat`
  empties `messages` and a per-chat count would silently miss a second
  question asked in a fresh chat. **Nothing about prompting reads PledgeTracker state.** The former
  `modal_close` and `longstop` triggers did, and since only the manipulation
  arm can open a pledge modal, that arm had prompt paths control could never
  reach — differential prompt exposure inside the instrument measuring the
  outcome. Rows written before this change carry the retired
  `timer`/`modal_close`/`longstop` trigger values; the vocabulary was renamed
  rather than reused so the two regimes stay distinguishable in `events`.
  The form opens IN-APP via
  `FilloutPopupEmbed` (same pattern as `survey-banner.tsx`), carrying
  `user_id` + `chat_session_id` + `cohort` as parameters (matching the form's
  hidden fields); trigger/context stay in the event log. Passing the cohort
  reverses the original no-self-unblinding rule — it is readable in the iframe
  URL — and it is a CONVENIENCE COPY only: `study_participants/{uid}` stays
  authoritative, because it alone carries `assignment_source` and so tells a
  real participant from a `?sg=` tester. A Fillout row's `cohort` cannot do
  that on its own. While the
  study is on, the study questionnaire is the ONLY thing anyone is asked for,
  app-wide: `StudyStatusProvider` holds one kill-switch subscription and
  `useStudyRunning()` suppresses the general feedback banner, the newsletter
  step after login, and the Wahl-Swiper feedback card. The rule ignores the
  cohort and consent, so no arm is exposed differently, and everything returns
  the moment the kill switch goes off.
- **Analysis joins**: `study_participants/{uid}` ↔ `chat_sessions.user_id`
  (sessions are also stamped `study_cohort` + `is_pledge_study`) ↔
  `page_visits.user_id`/`chat_session_ids` (dwell time) ↔ the questionnaire's
  `user_id` + `chat_session_id` answers. The uid is the Firebase anonymous uid
  throughout.
- **Forcing a variant** (`web/lib/pledge-study/variant-override.ts`): append
  `?sg=a` (consented control), `?sg=b` (consented manipulation), `?sg=x`
  (declined) in a study context; `?sg=off` clears it. Works in dev AND prod,
  including before launch — an override also forces the study on for that
  browser, client-side only, so the prod kill switch being off does not block
  testing. The values are opaque so a participant cannot read their arm off the
  URL; there is deliberately no signing or validation, since the repo is public
  and the bundle is inspectable. Persisted per tab in sessionStorage, ignored
  for Prolific participants.
  **Forced rows are flagged** `assignment_source: 'override'` (plus
  `override_variant`, `override_at`) and MUST be excluded from analysis. The
  flag write touches marker fields ONLY, never `consent_answer`/`cohort`, so
  it cannot destroy a real record — but **use a fresh browser profile**: an
  override link opened in a genuine participant's profile flags that
  participant out of the study. Two caveats: an override link bypasses the kill
  switch, and variants a/b can submit the real questionnaire, which Fillout
  records without the flag (cross-reference on `user_id` to exclude).
- Known simplifications: a prompt can land while another dialog is open (the
  triggers are time- and turn-based, not idle-based); the kill switch is
  client-read only
  (default-off hides everything until the snapshot arrives); a second device
  is a new participant (anonymous auth — accepted trade-off).

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
  store; embeddings are Gemini `gemini-embedding-2` at 3072 dimensions, COSINE
  distance. Do not mix models or dimensions — it breaks index parity. Treat
  `EMBEDDING_DIM` / `EMBEDDING_MODEL` in `setup_collection.py` as immutable
  after the first run.

  A collection name cannot prove which model produced its vectors, and OpenAI's
  `text-embedding-3-large` is also 3072-dimensional, so the dimension guard
  alone would pass on a mixed store. Every read and write therefore calls
  `setup_collection.check_fingerprint()`, which compares the collection's
  recorded provider/model/dim against the running configuration and raises on a
  mismatch.

  Note that `get_embeddings()` still falls back to OpenAI when
  `EMBEDDING_PROVIDER` is unset, so `ai-backend/.env` must set it — copy
  `.env.example`. Without it, ingestion and retrieval fail at the fingerprint
  check rather than reading the corpus.
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

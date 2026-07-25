<!--
SPDX-FileCopyrightText: 2025 wahl.chat

SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-->

# Firebase

Firebase configuration for [wahl.chat](https://wahl.chat/) — Firestore rules, Storage rules, Cloud Functions, and seed data.

## Directory Structure

```
firebase/
├── functions/           # Cloud Functions (Python 3.11)
│   ├── main.py          # Function handlers (PDF processing, vector store indexing)
│   ├── models.py        # Data models
│   └── requirements.txt # Python dependencies
├── firestore_data/      # Seed data for Firestore
│   ├── dev/             # Development environment data
│   └── prod/            # Production environment data
├── firebase.json        # Firebase project configuration
├── firestore.rules      # Firestore security rules
├── firestore.indexes.json
├── storage.rules        # Storage security rules
└── .firebaserc          # Project aliases (dev/prod)
```

## Prerequisites

```bash
npm install -g firebase-tools
firebase login

# For data import/export:
npm install -g node-firestore-import-export
```

## Cloud Functions Setup

The Cloud Functions are written in Python 3.11 and handle PDF document processing (splitting, embedding via OpenAI, indexing into Qdrant).

Dependencies are managed via `functions/requirements.txt`. To install locally for development:

```bash
cd functions
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Deploying Firebase Changes

First select your target environment:

```bash
firebase use dev    # or: firebase use prod
```

Then deploy:

```bash
firebase deploy --only firestore:rules      # Firestore security rules
firebase deploy --only firestore:indexes     # Firestore indexes
firebase deploy --only storage               # Storage security rules
firebase deploy --only functions             # All Cloud Functions
firebase deploy --only functions:FUNC_NAME   # A specific function
```

## Seeding Data

The application supports multiple election contexts (e.g., Bundestagswahl 2025, Landtagswahl Baden-Württemberg 2026). Each context has its own set of parties and proposed questions.

### Data Files

```
firestore_data/dev/
├── contexts.json                                         # All contexts
├── parties_bundestagswahl-2025.json                      # Parties for BTW 2025
├── parties_landtagswahl-baden-wuerttemberg-2026.json     # Parties for LTW BW 2026
├── parties_kommunalwahl-muenchen-2026.json               # Parties for KW München 2026
├── proposed_questions_bundestagswahl-2025.json           # Proposed questions for BTW 2025
├── proposed_questions_landtagswahl-baden-wuerttemberg-2026.json
└── proposed_questions_kommunalwahl-muenchen-2026.json
```

### Firestore Structure

```
contexts/{context_id}
├── context_id, name, type, date, ...
├── parties/{party_id}
│   └── party_id, name, long_name, manifesto_url, candidate, ...
└── proposed_questions/{party_id}/questions/{question_id}
    └── content, ...
```

### Seeding with the Python Script (Recommended)

The seed script's default target is the **local Firestore emulator**: with
`SEED_TARGET` unset it hard-exits unless `FIRESTORE_EMULATOR_HOST` is set, so a
local run can never accidentally write to a real project.

**Seeding a real project (dev/prod)** is supported today by running the script
locally with credentials and `SEED_TARGET=real` — guarded: it requires an
explicit `GOOGLE_CLOUD_PROJECT`, refuses to run with `FIRESTORE_EMULATOR_HOST`
set, and seeding prod (`wahl-chat`) additionally requires a matching
`SEED_CONFIRM_PROJECT`. Automating this on merge via Workload Identity is
envisioned and will land with the proper deployment (Terraform) workstream — see
`infra/README.md`.

Run from the repo root:

```bash
FIRESTORE_EMULATOR_HOST=localhost:8081 make seed-local
```

Or from the `firebase/` directory:

```bash
FIRESTORE_EMULATOR_HOST=localhost:8081 python scripts/seed_firestore.py
```

The script requires `firebase-admin`. The `make seed-local` target uses the ai-backend's uv environment automatically. To run standalone:

```bash
cd firebase && python -m venv venv && source venv/bin/activate
pip install firebase-admin google-auth
python scripts/seed_firestore.py
```

### Seeding with firestore-import (Manual)

Run from this (`firebase/`) directory:

```bash
# Seed contexts
firestore-import -a ../ai-backend/wahl-chat-dev-firebase-adminsdk.json \
  -n contexts -b firestore_data/dev/contexts.json -y

# Seed parties for a specific context
firestore-import -a ../ai-backend/wahl-chat-dev-firebase-adminsdk.json \
  -n contexts/bundestagswahl-2025/parties \
  -b firestore_data/dev/parties_bundestagswahl-2025.json -y
```

### Adding a New Context (e.g. a new election)

1. Add the context to `firestore_data/dev/contexts.json`
2. Create `firestore_data/dev/parties_{context_id}.json`
3. Create `firestore_data/dev/proposed_questions_{context_id}.json`
4. Run `FIRESTORE_EMULATOR_HOST=localhost:8081 make seed-local` from the repo root

**Required retrieval-scoping fields on the context document** (the chat backend scopes
RAG retrieval by these — see `ai-backend/src/models/context.py`):

- `region_path` — **always set explicitly.** ISO 3166-2 ancestry path, most-general
  first. Federal: `["DE"]`. Landtagswahl BW: `["DE", "DE-BW"]`. Municipal München:
  `["DE", "DE-BY", "DE-BY-MUC"]`. If omitted it silently defaults to federal `["DE"]`
  and the Land's own manifestos/votes become invisible to retrieval (the backend logs a
  warning when the field is missing).
- `legislature_period_id` — set for contexts with vote data: the abgeordnetenwatch
  `parliament_period` id. Look it up (or add a new row) in
  `ai-backend/src/ingestion/connectors/abgeordnetenwatch/legislature_config.py`, which
  also drives the current-vs-historic term window.
- `level` — `"federal"` | `"state"` | `"municipal"`; drives topic-relevance
  down-ranking. Omitted = treated as federal.
- `date` — election date; used to resolve the term window when a region has multiple
  configured periods.

Example (Landtagswahl) — abridged to the scoping fields:

```json
{
  "context_id": "landtagswahl-bw-2026",
  "type": "election",
  "date": "2026-03-08",
  "region_path": ["DE", "DE-BW"],
  "legislature_period_id": 165,
  "level": "state"
}
```

Corpus side: make sure the election's votes are ingested (the AW connector is
parameterized by `AW_LEGISLATURE_ID`; manifestos ingest all parliament periods since
2020 automatically). Mirror the context into `firestore_data/prod/contexts.json` when it
should exist in production.

## Managing Data

### Importing party data from dev to prod

1. Export parties: `firestore-export --accountCredentials ../ai-backend/wahl-chat-dev-firebase-adminsdk.json --backupFile firestore_data/dev/parties.json --nodePath parties`
2. Copy `firestore_data/dev/parties.json` to `firestore_data/prod/parties.json`
3. **Important**: Replace dev storage URLs with prod URLs:
   - Find: `https://storage.googleapis.com/wahl-chat-dev.firebasestorage.app`
   - Replace: `https://storage.googleapis.com/wahl-chat.firebasestorage.app`
4. Import parties: `firestore-import --accountCredentials ../ai-backend/wahl-chat-firebase-adminsdk.json --backupFile firestore_data/prod/parties.json --nodePath parties`

### Exporting proposed questions between parties

```bash
# Export from source party
firestore-export --accountCredentials ../ai-backend/wahl-chat-dev-firebase-adminsdk.json \
  --backupFile firestore_data/proposed_questions_afd_questions.json \
  --nodePath proposed_questions/afd/questions -p

# Import to target party
firestore-import --accountCredentials ../ai-backend/wahl-chat-dev-firebase-adminsdk.json \
  --backupFile firestore_data/proposed_questions_afd_questions.json \
  --nodePath proposed_questions/bsw/questions
```

### Moving proposed questions from dev to prod

```bash
# Export from dev
firestore-export --accountCredentials ../ai-backend/wahl-chat-dev-firebase-adminsdk.json \
  --backupFile firestore_data/proposed_questions.json --nodePath proposed_questions -p

# Import to prod
firestore-import --accountCredentials ../ai-backend/wahl-chat-firebase-adminsdk.json \
  --backupFile firestore_data/proposed_questions.json --nodePath proposed_questions
```

## Moving a Context from Dev to Prod

### 1. Prepare data files

```bash
cd firestore_data

cp dev/contexts.json prod/contexts.json
cp dev/parties_{context_id}.json prod/parties_{context_id}.json
cp dev/proposed_questions_{context_id}.json prod/proposed_questions_{context_id}.json
```

### 2. Update Firebase Storage URLs

Replace dev storage URLs with prod URLs in all copied files:
- Find: `https://storage.googleapis.com/wahl-chat-dev.firebasestorage.app`
- Replace: `https://storage.googleapis.com/wahl-chat.firebasestorage.app`

### 3. Upload assets to prod storage

Ensure all referenced assets (logos, PDFs, etc.) exist in the prod Firebase Storage bucket under the same paths as in dev.

### 4. Seed production Firestore

Production seeding is **intentionally blocked** — the seed
script hard-exits unless `FIRESTORE_EMULATOR_HOST` points at a local emulator,
so it can never write to a real Firestore instance. Seeding production data is
a manual operator step deferred (e.g. via
`firestore-import` with production credentials, as described above).

### 5. Ensure the Qdrant corpus covers the new region

The Qdrant vector store is **not** part of Firestore seeding and is not
documented here — it is a single shared corpus per environment filled by the
ingestion pipeline, not per-context collections. See the repo-root `AGENTS.md`
("Qdrant collection design" and "Running ingestion connectors") for the design
and how the corpus is populated. Moving a context to prod creates no Qdrant
collection; just confirm the ingestion jobs have populated chunks for the
context's region (the region filter must match at query time).

### 6. Verify

1. Check the Firebase Console to confirm data was imported correctly
2. Test the context in the production application
3. Verify party responses and proposed questions work as expected

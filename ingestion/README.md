<!--
SPDX-FileCopyrightText: 2026 wahl.chat

SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-->

# Ingestion

The corpus layer for [wahl.chat](https://wahl.chat/): the connectors and runner that
fill the Qdrant corpus, the collection definition, and the embedding factory that
fixes its vector space.

Built with Qdrant, LangChain embeddings, and Pydantic. Dependencies are managed with
**uv** — this package is a member of the workspace rooted at the repo's top-level
`pyproject.toml`.

The Pydantic models in `src/ingestion/schemas.py` are the single source of truth for
the corpus data contract (chunk payloads, source items, authority tiers).

## Relationship to `ai-backend/`

**The two packages are independent: neither imports the other.** That keeps this
package's connector dependencies (trafilatura, pypdf, beautifulsoup4,
google-cloud-storage) out of the chat image, and keeps the backend's web stack out
of the Job image.

Query-time retrieval is *not* here: `retrieve()` is a backend concern and lives in
`ai-backend/src/retrieve.py`.

What the two must agree on lives in `corpus-contract.json` at the repo root — the
embedding space, collection name, governance levels, payload enums, and the 36 AW
legislature periods. Both packages read it; both images copy it in. A few modules
are duplicated verbatim and marked `GENERATED-PAIR` in their headers — edit both
copies.

Three layers stop the two drifting apart:

1. **Parity tests** in each suite — each package's constants vs the contract.
2. **`scripts/check_contract_parity.py`** in pre-commit — the duplicated modules
   have not diverged.
3. **`check_fingerprint()`** at runtime — `corpus.py` stamps the provider/model/dim
   that produced the vectors into the collection itself, and the backend verifies
   it on every query. Anything that slips past the first two still fails loudly
   rather than returning cross-space garbage.

## Setup

> Need help? Contact us at [info@wahl.chat](mailto:info@wahl.chat).

### 1. Install dependencies

One `uv sync` at the **repo root** installs both workspace members into a shared
environment:

```bash
uv sync            # all dependencies, including the dev group
uv sync --no-dev   # runtime dependencies only
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

`OPENAI_API_KEY` is always required. Add `DIP_API_KEY` for the Bundestag speeches
connector and, optionally, `AW_API_KEY` for Abgeordnetenwatch when rate-limited.

### 3. Create the collection (once, idempotent)

```bash
QDRANT_URL=http://localhost:6333 uv run python -m ingestion.setup_collection
```

## Running connectors

All registry connectors go through one entrypoint:

```bash
uv run python -m ingestion.run --connector <id>
```

Registered IDs: `abgeordnetenwatch_votes`, `bundestag_speeches`,
`openparliament_tv`, `manifesto_uploads`, `manifestos`.

From the repo root the `Makefile` wraps the common cases and wires the local Qdrant
URL automatically (run `make stores-up` first):

```bash
make run-abgeordnetenwatch-votes          # federal votes
make run-all-landtage-votes               # all 16 Landtage
make run-speeches ARGS="--batch-size 25"  # DIP speeches
make run-manifestos ARGS="--dry-run"      # parse only, zero embedding cost
make speeches-stats                       # read-only Qdrant verification
```

In production the same `ingestion.run` code path runs as a Cloud Run Job from the
image built by `ingestion/Dockerfile`, with `CONNECTOR_ID` set in the job spec.
Deployment and scheduling are a planned Terraform workstream.

Ingestion must tolerate the 15-minute scheduled-job cap: runs are resumable via a
stored cursor, and `--time-budget` stops a run cleanly before the cap.

## Tests

```bash
uv run pytest              # from this directory
```

Or `make test-backend` from the repo root, which runs both members' suites.

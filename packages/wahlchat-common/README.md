<!--
SPDX-FileCopyrightText: 2026 wahl.chat

SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-->

# wahlchat-common

Code shared by `ai-backend` and `ingestion`.
Each image depends on this package. Neither image depends on the other.

| Module | Contents |
|---|---|
| `corpus.py` | collection name, embedding constants, fingerprint check |
| `embeddings.py` | `get_embeddings()` |
| `enums.py` | `SourceType` and `AuthorityTier` |
| `governance_levels.py` | `ALL_LEVELS` and the level constants |
| `legislature_config.py` | the 36 AW parliament periods |
| `pledge_tracker.py` | `PledgeRecord` and `PledgeTimelineEvent` |
| `vertex_credentials.py` | Vertex service-account resolution |

Put further shared code in this package.

## Dependency rule

Every dependency of this package is already a direct dependency of both images.
A new dependency here is installed in both images.

Collection creation stays in `ingestion/src/ingestion/setup_collection.py`.
Query-time retrieval stays in `ai-backend/src/retrieve.py`.

## Fingerprint

The chat service and the ingestion Job receive environment variables separately.
One process can use a different `EMBEDDING_MODEL` than the other.
`check_fingerprint()` stores the provider, model, and dimension in the collection.
Read and write both compare that record with the running process.

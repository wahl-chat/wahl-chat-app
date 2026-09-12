<!--
SPDX-FileCopyrightText: 2026 wahl.chat

SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-->

# wahlchat-common

Code shared by the Python components. `ai-backend` and `ingestion` both depend on
it; **neither depends on the other**.

Today that is the corpus contract plus Vertex credentials:

| Module | What it holds |
|---|---|
| `corpus.py` | collection name, embedding constants, fingerprint read + verify |
| `embeddings.py` | `get_embeddings()` — the factory both sides embed with |
| `enums.py` | `SourceType` / `AuthorityTier` payload values |
| `governance_levels.py` | `ALL_LEVELS` and the level constants |
| `legislature_config.py` | the 36 AW parliament periods + term-window derivation |
| `vertex_credentials.py` | Vertex service-account resolution |

Anything else the components come to share belongs here too — the Firebase
functions are Python and could become a third consumer.

## The one rule

Every dependency declared here is already a direct dependency of both consumers,
so this package adds nothing to either Docker image. **Keep it that way.** A heavy
dependency added for one consumer lands in every image that installs this package
— which is the cost the split exists to avoid.

The write side (collection creation, index specs, `write_fingerprint`) stays in
`ingestion/setup_collection.py`; query-time retrieval stays in
`ai-backend/src/retrieve.py`.

## Drift

Sharing the code removes source drift by construction. What it cannot remove is
**deployment** drift: the chat service and the ingestion Job get their env
separately, so one could run with a different `EMBEDDING_MODEL` than the other.
That is what `check_fingerprint()` is for — the provider/model/dim that produced
the vectors is stored in the collection and verified on read and on write.

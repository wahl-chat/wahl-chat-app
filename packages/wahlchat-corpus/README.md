<!--
SPDX-FileCopyrightText: 2026 wahl.chat

SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-->

# wahlchat-corpus

The contract `ai-backend` and `ingestion` share about the Qdrant corpus. Both
depend on this package; **neither depends on the other**.

| Module | What it holds |
|---|---|
| `corpus.py` | collection name, embedding constants, fingerprint read + verify |
| `embeddings.py` | `get_embeddings()` — the factory both sides embed with |
| `enums.py` | `SourceType` / `AuthorityTier` payload values |
| `governance_levels.py` | `ALL_LEVELS` and the level constants |
| `legislature_config.py` | the 36 AW parliament periods + term-window derivation |
| `vertex_credentials.py` | Vertex service-account resolution |

Every dependency here is already a direct dependency of both consumers, so this
package adds nothing to either Docker image. Keep it that way — anything heavier
belongs in the package that needs it.

The write side (collection creation, index specs, `write_fingerprint`) stays in
`ingestion/setup_collection.py`; query-time retrieval stays in
`ai-backend/src/retrieve.py`.

## Drift

Sharing the code removes source drift by construction. What it cannot remove is
**deployment** drift: the chat service and the ingestion Job get their env
separately, so one could run with a different `EMBEDDING_MODEL` than the other.
That is what `check_fingerprint()` is for — the provider/model/dim that produced
the vectors is stored in the collection and verified on read and on write.

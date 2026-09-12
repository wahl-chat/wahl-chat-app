# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Shared pytest setup for the ingestion test suite.

Several modules freeze env-derived values at import time (setup_collection's
EMBEDDING_MODEL / EMBEDDING_DIM / COLLECTION_NAME), so the os.environ.setdefault()
calls below must run before any ingestion import happens. The values are safe
dummies — no test in this suite performs a live embedding call.

qdrant_client.QdrantClient is replaced with a MagicMock at module scope so no
test can accidentally open a network connection through the default client
class. Tests that need a REAL local Qdrant (test_qdrant_schema.py) deliberately
bypass the patch by importing the class from ``qdrant_client.qdrant_client``,
and skip when no local store is reachable.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Set required env vars before any ingestion imports happen.
# ---------------------------------------------------------------------------
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("OPENAI_API_KEY", "dummy-openai-key-for-ci")
os.environ.setdefault("GOOGLE_API_KEY", "dummy-google-key-for-ci")

from unittest.mock import MagicMock, patch as _patch  # noqa: E402

_qdrant_client_mock = MagicMock()
_qdrant_client_mock.get_collections.return_value = MagicMock(collections=[])
_qdrant_client_mock.search.return_value = []

_qdrant_patch = _patch("qdrant_client.QdrantClient", return_value=_qdrant_client_mock)
_qdrant_patch.start()

# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""The same import-time environment as the ingestion suite, whose feed
fixtures these tests reuse: dummy settings, and no real Qdrant client."""

from __future__ import annotations

import os

os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("OPENAI_API_KEY", "dummy-openai-key-for-ci")
os.environ.setdefault("GOOGLE_API_KEY", "dummy-google-key-for-ci")

from unittest.mock import MagicMock, patch as _patch  # noqa: E402

_qdrant_patch = _patch("qdrant_client.QdrantClient", return_value=MagicMock())
_qdrant_patch.start()

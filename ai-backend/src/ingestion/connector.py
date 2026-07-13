# SPDX-FileCopyrightText: 2025 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
BaseConnector — abstract base class for all data source connectors.

Synchronous single-pass embed path:
    discover(since: Optional[int]) -> list[str]
    fetch(external_id: str) -> dict
    normalize(raw: dict) -> list[ChunkRecord]

The runner (run.py) owns embed + upsert; connectors are pure data-transform.
The cursor (since) is derived by the runner from Qdrant max(external_id) for
the connector's source_type. No Firestore. No GCS. Embedding is inline.

Each concrete connector must implement all three abstract methods:
    1.  discover   — list external IDs to fetch, filtered by cursor
    2.  fetch      — retrieve raw payload for one external ID
    3.  normalize  — transform raw payload into a list[ChunkRecord]
"""

from abc import ABC, abstractmethod
from typing import Optional

from .schemas import ChunkRecord


class BaseConnector(ABC):
    """Abstract base for all wahl.chat V2 data source connectors.

    Single synchronous embed path:
        discover(since) -> fetch -> normalize -> [runner embeds + upserts]

    The runner derives the cursor from Qdrant max(external_id) for this
    connector's source_type and passes it to discover(). No watermark methods,
    no GCS methods, no Firestore methods.
    """

    @abstractmethod
    def discover(self, since: Optional[int]) -> list[str]:
        """Return list of external IDs to fetch, filtered by the cursor.

        Args:
            since: Max external_id already committed to Qdrant for this
                   connector's source_type, or None on first run (fetch all).

        Returns:
            List of external ID strings sorted ascending (oldest first).
        """
        ...

    @abstractmethod
    def fetch(self, external_id: str) -> dict:
        """Fetch raw data for one item from the upstream source.

        Args:
            external_id: String ID returned by discover().

        Returns:
            Raw response dict (verbatim).
        """
        ...

    @abstractmethod
    def normalize(self, raw: dict) -> list[ChunkRecord]:
        """Transform raw payload into validated ChunkRecords.

        Args:
            raw: Dict returned by fetch().

        Returns:
            List of ChunkRecord instances (may be empty — runner skips upsert).

        Raises:
            ValueError: If the raw payload is malformed or produces no usable
                        chunks (runner skip-and-continues; cursor does not advance).
        """
        ...

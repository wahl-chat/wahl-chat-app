# SPDX-FileCopyrightText: 2026 wahl.chat
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
    """Abstract base for all wahl.chat data source connectors.

    Single synchronous embed path:
        discover(since) -> fetch -> normalize -> [runner embeds + upserts]

    The runner derives the cursor from Qdrant max(external_id) for this
    connector's source_type and passes it to discover(). No watermark methods,
    no GCS methods, no Firestore methods.

    Required class attribute:
        source_type: The SourceType value string this connector produces
                     (e.g. ``"vote_record"``). The runner reads it to scope
                     the Qdrant cursor scroll — a connector without it fails
                     at runtime, so declare it on every subclass.

    Optional class attribute:
        source: Connector discriminator within a shared source_type
                (e.g. ``"dip"`` / ``"op"`` — both write
                ``"parliamentary_speech"``). When set, the runner scopes the
                cursor to this source so two connectors sharing one
                source_type keep independent cursors. Default None: the
                cursor is scoped by source_type alone.
    """

    # Required on every concrete connector (annotation only — no default, so a
    # subclass that forgets it raises AttributeError in the runner, loudly).
    source_type: str

    # Optional discriminator within a shared source_type (see class docstring).
    source: Optional[str] = None

    # Runner-bound store handle (see bind_store). None until the runner binds.
    _store_client = None
    _store_collection: Optional[str] = None

    def bind_store(self, qdrant, collection_name: str) -> None:  # noqa: ANN001
        """Hand the connector the runner's store handle before discover().

        Store-aware discovery (e.g. set-difference against already-ingested
        ids) must read the SAME client/collection the runner will upsert into;
        a connector-constructed client can silently diverge under an injected
        test client, a non-default collection, or a migration. Connectors that
        never read the store simply ignore the stored references.
        """
        self._store_client = qdrant
        self._store_collection = collection_name

    @property
    def cursor_source(self) -> Optional[str]:
        """Source scope for the runner's cursor read. Defaults to ``source``.

        The runner derives ``since`` from max(external_id) scoped to
        ``cursor_source`` (when not None). Override with a plain class attribute
        when the cursor must NOT be scoped to this connector's own ``source`` —
        e.g. the DIP speeches connector sets ``cursor_source = None`` because op
        progressively supersede-deletes dip points, so a dip-scoped max would
        walk BACKWARD; the cross-source max over the shared source_type is a
        valid, non-regressing floor (op external_ids share the YYYYMMDD scale).
        """
        return self.source

    @abstractmethod
    def discover(self, since: Optional[int]) -> list[str]:
        """Return list of external IDs to fetch, filtered by the cursor.

        IMPORTANT — do NOT implement this as a naive ``external_id > since``
        filter. The cursor is max(external_id) over COMMITTED points, so an
        item that transiently FAILED below that watermark would be permanently
        dropped by a strict ``> since`` filter (the cursor already advanced
        past it). Correct discovery strategies are:

          * set-difference: enumerate the source's ids and exclude only ids
            already present in the store (re-surfaces every failure), or
          * lookback floor: filter at ``since − LOOKBACK`` so recent failures
            below the watermark are re-discovered; the runner's cheap
            already-present skip makes the re-scan affordable.

        Args:
            since: Max external_id already committed to Qdrant for this
                   connector's source_type (and source, when set), or None on
                   first run (fetch all).

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

    def post_upsert(
        self, qdrant, collection_name: str, chunks: list[ChunkRecord]
    ) -> int:  # noqa: ANN001
        """Optional hook — called by the runner AFTER each successful item upsert.

        Source-specific follow-up policy belongs here, on the connector, not in
        the generic runner. Example: the openparliament_tv connector supersedes
        the just-upserted speeches' DIP twins (graft PDF + delete duplicate).

        Default: no-op. Override only when the connector needs store-side
        follow-up after its chunks are durably written.

        Args:
            qdrant:          Initialised QdrantClient.
            collection_name: The collection the chunks were upserted into.
            chunks:          The just-upserted ChunkRecords (one item's chunks).

        Returns:
            Number of store-side follow-up actions performed (0 for the no-op).
        """
        return 0

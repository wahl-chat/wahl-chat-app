# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
AbgeordnetenwatchVotesConnector — synchronous single-pass connector.

This connector implements the 3-method synchronous ABC
(discover/fetch/normalize) and produces list[ChunkRecord] directly from
normalize() — no Firestore, no GCS, no work_queue, no matcher dual-write.

The runner (run.py) owns embed + upsert; this connector is pure data-transform.
The cursor (since) is derived by the runner from Qdrant max(external_id) for
"vote_record" and passed to discover() — no watermark methods needed.

Security notes:
    GDPR Art. 9 wall: NO code path reads users/{uid}.  This invariant
    is enforced by a grep-based static test in test_connector.py::TestGdprWall.

    Skip-and-warn on zero-tally: a poll producing zero usable tallies
    raises ValueError so run_connector skip-and-continue applies; the cursor
    does not advance past it (idempotent upsert handles re-processing).

    external_id integer index: normalize() stamps raw int poll_id
    (no "aw_poll:" prefix) so the Qdrant integer cursor stays sound.
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from datetime import date as date_type
from typing import Optional

from qdrant_client import QdrantClient

from src.ingestion.connector import BaseConnector
from src.ingestion.connectors.abgeordnetenwatch.client import AWClient
from src.ingestion.connectors.abgeordnetenwatch.legislature_config import (
    LEGISLATURE_CONFIG,
)
from src.ingestion.connectors.abgeordnetenwatch.mappers import corpus as corpus_mapper
from src.ingestion.ids import compute_source_item_id
from src.ingestion.schemas import AuthorityTier, ChunkRecord, SourceType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Zero-polls grace window (days since the period's date_from). A legitimately
# NEW term (e.g. BW/RP 2026-2031 in their first weeks) plausibly has zero polls
# for a while — only a period older than this window turns "zero polls from the
# API" into a hard misconfiguration error.
_ZERO_POLLS_GRACE_DAYS = 90


@dataclass(frozen=True)
class _SourceItem:
    """Frozen source-item envelope fed to corpus_mapper.chunk_poll().

    Satisfies the structural SourceItemLike protocol in mappers/corpus.py —
    the five attributes chunk_poll() reads from its first argument.
    """

    source_item_id: uuid.UUID
    region: str
    authority_tier: AuthorityTier
    source_type: SourceType
    publish_date: date_type


# ---------------------------------------------------------------------------
# AbgeordnetenwatchVotesConnector
# ---------------------------------------------------------------------------


class AbgeordnetenwatchVotesConnector(BaseConnector):
    """Connector for Abgeordnetenwatch poll votes → vote_record ChunkRecords.

    Synchronous single-pass connector:
        discover(since) → fetch → normalize → [runner embeds + upserts]

    The cursor (since) is the max external_id (raw integer poll_id) already
    committed to Qdrant for "vote_record", derived by the runner via
    get_cursor().  No Firestore, no GCS, no work queue.

    Args:
        legislature_id: AW legislature (parliament_period) ID to scope discovery.
                        None (default) reads AW_LEGISLATURE_ID from the
                        environment at CONSTRUCTION time (not import time, so a
                        long-lived process can construct one connector per
                        legislature), falling back to 111 (19th Bundestag).
    """

    # Class attribute: used by runner.get_cursor() to scope the Qdrant scroll.
    source_type: str = SourceType.VOTE_RECORD.value

    def __init__(
        self,
        legislature_id: Optional[int] = None,
    ) -> None:
        # Env read lives in the __init__ BODY: an import-time default arg
        # would freeze the value for the process lifetime and force one process
        # invocation per legislature.
        if legislature_id is None:
            legislature_id = int(os.getenv("AW_LEGISLATURE_ID", "111"))
        self._legislature_id = legislature_id

        cfg = LEGISLATURE_CONFIG.get(legislature_id)
        if cfg is None:
            raise ValueError(
                f"Legislature {legislature_id} not in LEGISLATURE_CONFIG. "
                f"Add a LegislatureConfig row in legislature_config.py before running."
            )
        # Period key (globally unique AW parliament_period int).
        self._period_id: int = cfg.parliament_period_id
        # ISO 3166-2 region code (e.g. "DE-BY" for Bayern, "DE" for Bundestag).
        self._region: str = cfg.region
        # German Wahlperiode number (Bundestag rows only; None for Landtage).
        self._wahlperiode: Optional[int] = cfg.wahlperiode
        # Period start date — drives the zero-polls grace window.
        self._period_date_from: str = cfg.date_from

        # Paced AW API client.
        self._client = AWClient()

        # Lazy Qdrant client for per-legislature cursor queries.
        # Initialised on first call to _get_qdrant().
        self._qdrant: Optional[QdrantClient] = None

    # ------------------------------------------------------------------
    # 1a. Qdrant lazy singleton (per-legislature cursor)
    # ------------------------------------------------------------------

    def _get_qdrant(self) -> QdrantClient:
        """Return the per-instance Qdrant client, initializing on first call.

        Mirrors the module-level singleton in retrieve.py (lines 52-65).
        Kept as an instance method so tests can monkeypatch it per-connector.
        """
        if self._qdrant is None:
            self._qdrant = QdrantClient(
                url=os.getenv("QDRANT_URL", "http://localhost:6333"),
                api_key=os.getenv("QDRANT_API_KEY"),
            )
        return self._qdrant

    def _get_ingested_poll_ids(self) -> set[int]:
        """Return the set of AW poll ids already ingested for this legislature.

        Scrolls all vote_record chunks filtered by legislature_period_id and collects
        their external_id (= AW poll id). Used for set-difference discovery.

        This replaces a max(external_id) high-water mark, which permanently lost any
        poll that was skipped/failed below the max on a prior run (the max advanced past
        it and the strict ``id > cursor`` filter never re-surfaced it). Set-difference is
        gap-free and self-healing: a poll missing from Qdrant is always re-attempted, and
        a permanently-unprocessable poll simply stays absent without blocking newer polls.
        """
        from qdrant_client import models as qdrant_models
        from src.ingestion.setup_collection import COLLECTION_NAME

        qdrant = self._get_qdrant()
        ingested: set[int] = set()
        next_offset: Optional[qdrant_models.ExtendedPointId] = None
        scroll_filter = qdrant_models.Filter(
            must=[
                qdrant_models.FieldCondition(
                    key="source_type",
                    match=qdrant_models.MatchValue(value="vote_record"),
                ),
                qdrant_models.FieldCondition(
                    key="legislature_period_id",
                    match=qdrant_models.MatchValue(value=self._period_id),
                ),
            ]
        )
        while True:
            points, next_offset = qdrant.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=scroll_filter,
                limit=1000,
                offset=next_offset,
                with_payload=["external_id"],
                with_vectors=False,
            )
            for p in points:
                ext = p.payload.get("external_id") if p.payload else None
                if isinstance(ext, int):
                    ingested.add(ext)
            if next_offset is None:
                break
        return ingested

    # ------------------------------------------------------------------
    # 1b. discover — scoped to one legislature, per-legislature cursor
    # ------------------------------------------------------------------

    def discover(self, since: Optional[int]) -> list[str]:
        """Return poll ids to process for the configured legislature.

        Scopes to field_legislature.  Discovers via per-legislature SET DIFFERENCE
        against Qdrant (polls in the AW API minus polls already ingested) instead of the
        global `since` from run_connector() — the global cursor is dominated by high-ID
        Bundestag polls and would silently skip all lower-ID Landtag polls, and a max
        watermark permanently loses any poll skipped below the max on an earlier run.

        The global `since` argument from run_connector() is accepted (preserves
        the ABC contract) but IGNORED — set-difference supersedes it.

        Fail-fast (with grace window): zero polls from the raw API response is
        checked BEFORE the set-difference filter (a set-difference-filtered-to-empty
        result is normal on incremental runs). It raises ValueError ONLY when the
        configured period's date_from is older than _ZERO_POLLS_GRACE_DAYS —
        a legitimately NEW term (e.g. BW/RP right after their 2026 elections)
        plausibly has zero polls for weeks; in that case a warning is logged and
        [] is returned instead of aborting with a misleading
        "wrong parliament_period_id" error.

        Args:
            since: Global max external_id for "vote_record" from run_connector().
                   Accepted for ABC-contract compatibility but not used
                   (per-legislature set-difference supersedes it).

        Returns:
            List of poll id strings sorted ascending by integer poll ID for a stable,
            deterministic batch order across runs.
        """
        legislature_id = self._legislature_id

        # Fetch all polls for this legislature.
        polls = self._client.get_all("polls", {"field_legislature": legislature_id})

        # Fail-fast with grace window: zero polls from the raw API response
        # usually means a misconfigured parliament_period_id in LEGISLATURE_CONFIG.
        # MUST check BEFORE the set-difference filter — a set-difference-filtered-
        # to-empty result is normal on incremental runs. Exception: a legitimately
        # NEW term (period started within _ZERO_POLLS_GRACE_DAYS) plausibly has
        # zero polls for weeks — warn and return [] instead of aborting.
        if not polls:
            period_start = date_type.fromisoformat(self._period_date_from)
            period_age_days = (date_type.today() - period_start).days
            if period_age_days > _ZERO_POLLS_GRACE_DAYS:
                raise ValueError(
                    f"AW legislature {legislature_id} ({self._region}) returned zero polls "
                    f"from the API and its period started {period_age_days} days ago "
                    f"(> {_ZERO_POLLS_GRACE_DAYS}-day grace window). This usually means a "
                    f"wrong parliament_period_id in LEGISLATURE_CONFIG. "
                    f"Expected >0 polls for an established legislature."
                )
            logger.warning(
                "AW legislature %s (%s) returned zero polls, but its period started "
                "only %s days ago (<= %s-day grace window) — likely a legitimately "
                "new term with no polls yet. Returning no work.",
                legislature_id,
                self._region,
                period_age_days,
                _ZERO_POLLS_GRACE_DAYS,
            )
            return []

        # Drop malformed poll entries whose id is not an int (untrusted AW payload).
        # Applied on BOTH the incremental and the AW_REFRESH path — a
        # non-int id would crash str(p["id"]) sorting / fetch downstream.
        polls = [p for p in polls if isinstance(p.get("id"), int)]

        # Set-difference discovery: ingest polls present in the AW API but not yet in
        # Qdrant for this legislature. Gap-free and self-healing — a poll skipped/failed
        # on a prior run stays missing and is retried, and a permanently-unprocessable
        # poll keeps failing harmlessly without blocking newer polls (no high-water mark
        # to corrupt).
        #
        # AW_REFRESH=1 forces a full reconcile: return ALL polls so run.py's change-aware
        # upsert can re-write any whose content_hash changed (e.g. an AW tally corrected
        # after first ingest). Unchanged polls are skipped there without re-embedding.
        refresh = os.getenv("AW_REFRESH", "").strip().lower() in ("1", "true", "yes")
        if not refresh:
            ingested_ids = self._get_ingested_poll_ids()
            polls = [p for p in polls if p["id"] not in ingested_ids]

        # Optional date floor — read inside discover() so tests can monkeypatch per-call.
        aw_poll_since = os.getenv("AW_POLL_SINCE", "").strip()
        if aw_poll_since:
            # Plain string compare is valid for zero-padded YYYY-MM-DD dates.
            # Polls with a missing/empty field_poll_date are excluded when the floor is set.
            polls = [
                p
                for p in polls
                if (p.get("field_poll_date") or "") >= aw_poll_since
                and (p.get("field_poll_date") or "") != ""
            ]

        # Sort ASCENDING BY INTEGER POLL ID (not by field_poll_date) for a stable,
        # deterministic batch order. run.py processes the first batch_size ids per run;
        # on the next run those are ingested and drop out of the set-difference, so newer
        # polls surface. Sorting by date could reorder the batch window run-to-run.
        # (ids are guaranteed int by the isinstance filter above.)
        polls_sorted = sorted(polls, key=lambda p: p["id"])
        return [str(p["id"]) for p in polls_sorted]

    # ------------------------------------------------------------------
    # 2. fetch
    # ------------------------------------------------------------------

    def fetch(self, external_id: str) -> dict:
        """Fetch raw poll + votes payload for a single poll_id.

        Args:
            external_id: String poll id (e.g., "3602").

        Returns:
            Dict with keys "poll" (single poll item) and "votes" (list of vote items).
        """
        poll_id = int(external_id)
        poll_resp = self._client.get(f"polls/{poll_id}")
        poll = poll_resp["data"]
        votes = self._client.get_votes_for_poll(poll_id)
        return {"poll": poll, "votes": votes}

    # ------------------------------------------------------------------
    # 3. normalize — returns list[ChunkRecord] directly
    # ------------------------------------------------------------------

    def normalize(self, raw: dict) -> list[ChunkRecord]:
        """Build ChunkRecords directly from poll + votes payload.

        No SourceItemRecord, no matcher objects, no Firestore.
        The whole record build lives in corpus_mapper.chunk_poll(): topic
        extraction, relevance_levels derivation, envelope stamping (external_id
        = raw int poll_id, wahlperiode, legislature_period_id, region) and the
        envelope-inclusive content_hash. This method owns only the connector
        concerns: the legislature cross-check, publish_date parsing, the
        source-item stub, and raising ValueError on unusable input.

        Zero-tally guard:
            If the poll produces zero usable fraction tallies (all votes have
            fraction=[]), chunk_poll() returns an empty list and this method
            raises ValueError.

        Args:
            raw: Dict with keys "poll" (poll item dict) and "votes" (list).

        Returns:
            list[ChunkRecord] — one fully-stamped chunk per poll from
            chunk_poll(), each with external_id = poll_id (raw int).

        Raises:
            ValueError: If the poll has zero usable fraction tallies, an
                unparseable poll date, or belongs to a different legislature
                than this connector is configured for.
        """
        poll: dict = raw["poll"]

        poll_id: int = poll["id"]

        # Legislature cross-check: an operator error (e.g. fetching a
        # Bundestag poll under a Bayern connector) would silently stamp the
        # wrong region/legislature_period_id, so refuse rather than mislabel.
        poll_legislature_id = (poll.get("field_legislature") or {}).get("id")
        if poll_legislature_id != self._legislature_id:
            raise ValueError(
                f"AW poll {poll_id} belongs to legislature {poll_legislature_id!r} "
                f"but this connector is configured for legislature "
                f"{self._legislature_id} ({self._region}) — refusing to stamp a "
                f"foreign-legislature poll (skipping)."
            )

        poll_date_str: str = poll.get("field_poll_date") or ""
        try:
            publish_date = date_type.fromisoformat(poll_date_str)
        except (ValueError, TypeError):
            # A missing/unparseable poll date makes publish_date non-deterministic;
            # raise rather than fabricate date.today().
            raise ValueError(
                f"AW poll {poll_id} has missing or unparseable field_poll_date "
                f"{poll_date_str!r} — skipping to avoid fabricated publish_date."
            )

        # external_id_str for UUID determinism (raw integer, no prefix)
        external_id_str = str(poll_id)
        source_item_id = compute_source_item_id("vote_record", external_id_str)

        stub = _SourceItem(
            source_item_id=source_item_id,
            region=self._region,  # from LegislatureConfig
            authority_tier=AuthorityTier.FACTUAL_RECORD,
            source_type=SourceType.VOTE_RECORD,
            publish_date=publish_date,
        )

        # chunk_poll produces ONE fully-stamped ChunkRecord per poll (the
        # tallies live inside meta.vote_results, not one chunk per fraction).
        chunks = corpus_mapper.chunk_poll(
            stub,
            raw,
            wahlperiode=self._wahlperiode,  # None for Landtage
            legislature_period_id=self._period_id,  # from LegislatureConfig
        )

        # Zero-tally guard — chunk_poll returns [] when aggregate_fraction_tallies
        # finds no usable tallies; surface it as the runner's skip contract.
        if not chunks:
            raise ValueError(
                f"AW poll {poll_id} has zero usable tallies — "
                "all votes have fraction=[] or no votes at all. "
                "Skipping poll."
            )

        return chunks

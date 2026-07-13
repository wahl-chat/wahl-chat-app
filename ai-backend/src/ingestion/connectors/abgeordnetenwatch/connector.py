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
from datetime import date as date_type
from typing import Optional

from qdrant_client import QdrantClient

from src.ingestion.connector import BaseConnector
from src.ingestion.connectors.abgeordnetenwatch.client import AWClient
from src.ingestion.connectors.abgeordnetenwatch.legislature_config import (
    LEGISLATURE_CONFIG,
)
from src.ingestion.connectors.abgeordnetenwatch.topic_taxonomy_config import (
    get_relevance_levels,
)
from src.ingestion.connectors.abgeordnetenwatch.mappers import corpus as corpus_mapper
from src.ingestion.connectors.abgeordnetenwatch.mappers.corpus import (
    _normalize_fraction_label,
)
from src.ingestion.connectors.abgeordnetenwatch.mappers.stance import (
    aggregate_fraction_tallies,
)
from src.ingestion.ids import compute_source_item_id
from src.ingestion.schemas import AuthorityTier, ChunkRecord, SourceType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default Bundestag legislature ID (19th Bundestag, 2017-2021).
# Override via AW_LEGISLATURE_ID env var.
_DEFAULT_LEGISLATURE_ID = int(os.getenv("AW_LEGISLATURE_ID", "111"))

# Map from AW legislature (parliament_period) ID to German Wahlperiode number.
# 111 = 19th Bundestag (2017-2021), 132 = 20th Bundestag (2021-2025),
# 161 = 21st Bundestag (2025-).
_LEGISLATURE_TO_WAHLPERIODE: dict[int, int] = {
    111: 19,
    132: 20,
    161: 21,
}

# Canonical AW fraction-label → party slug map.
# Full name variants (as returned by the AW fractions endpoint full_name).
_AW_FRACTION_SLUG_MAP: dict[str, str] = {
    "spd": "spd",
    "cdu/csu": "cdu",
    "cdu": "cdu",
    "csu": "csu",
    "bündnis 90/die grünen": "gruene",
    "bündnis 90/die grüne": "gruene",
    "die grünen": "gruene",
    "grüne": "gruene",
    "fdp": "fdp",
    "afd": "afd",
    "alternative für deutschland": "afd",
    "die linke": "linke",
    "die linke.": "linke",
    "die linke. (gruppe)": "linke",
    "die linke (gruppe)": "linke",
    "linke": "linke",
    "bsw": "bsw",
    "bsw (gruppe)": "bsw",
    "fraktionslos": "fraktionslos",
}


def _full_name_to_slug(full_name: str) -> str:
    """Map an AW fraction full_name to a canonical party slug.

    Normalises away invisible formatting characters (the U+00AD soft hyphen AW
    puts in "BÜNDNIS 90/­DIE GRÜNEN"), lowercases and strips before lookup.
    Unknown names return "unbekannt".
    """
    clean = _normalize_fraction_label(full_name)
    return _AW_FRACTION_SLUG_MAP.get(clean, "unbekannt")


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
                        Defaults to 111 (19th Bundestag 2017-2021) or AW_LEGISLATURE_ID.
    """

    # Class attribute: used by runner.get_cursor() to scope the Qdrant scroll.
    source_type: str = SourceType.VOTE_RECORD.value

    def __init__(
        self,
        legislature_id: int = _DEFAULT_LEGISLATURE_ID,
    ) -> None:
        self._legislature_id = legislature_id

        # Validate legislature_id against LEGISLATURE_CONFIG; fail loudly on miss.
        cfg = LEGISLATURE_CONFIG.get(legislature_id)
        if cfg is None:
            raise ValueError(
                f"Legislature {legislature_id} not in LEGISLATURE_CONFIG (D-05). "
                f"Add a LegislatureConfig row in legislature_config.py before running."
            )
        # Period key (globally unique AW parliament_period int).
        self._period_id: int = cfg.parliament_period_id
        # ISO 3166-2 region code (e.g. "DE-BY" for Bayern, "DE" for Bundestag).
        self._region: str = cfg.region

        # Runtime fraction_id → party_slug map.
        # NOTE: self._fraction_map and discover()'s fractions API call are dead code
        # superseded by mappers/corpus.py::_canonical_party_slug().  The attribute
        # is retained here for backward-compat with tests that set it; discover()
        # no longer populates it (saves one AW /fractions call per run).
        self._fraction_map: dict[int, str] = {}

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

        Fail-fast: raises ValueError when the AW API returns zero polls
        for the configured legislature BEFORE applying the set-difference filter.
        Zero polls from the raw API response means the parliament_period_id in
        LEGISLATURE_CONFIG is wrong — an incremental run that is simply up-to-date
        would still have polls in the raw response (set-difference filters to empty,
        which is normal). Zero from the API is always an error.

        Args:
            since: Global max external_id for "vote_record" from run_connector().
                   Accepted for ABC-contract compatibility but not used
                   (per-legislature set-difference supersedes it).

        Returns:
            List of poll id strings sorted ascending by integer poll ID for a stable,
            deterministic batch order across runs.
        """
        legislature_id = self._legislature_id

        # NOTE: self._fraction_map / fractions API call is dead code — the active
        # slug-resolution path is mappers/corpus.py::_canonical_party_slug().
        # Removing the fractions call saves one AW API call per run.

        # Fetch all polls for this legislature.
        polls = self._client.get_all("polls", {"field_legislature": legislature_id})

        # Fail-fast: zero polls from the raw API response means a misconfigured
        # parliament_period_id in LEGISLATURE_CONFIG.  MUST check BEFORE the set-difference
        # filter — a set-difference-filtered-to-empty result is normal on incremental runs.
        if not polls:
            raise ValueError(
                f"AW legislature {legislature_id} ({self._region}) returned zero polls "
                f"from the API. This usually means a wrong parliament_period_id in "
                f"LEGISLATURE_CONFIG (D-05). Expected >0 polls for a configured legislature."
            )

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
            polls = [
                p
                for p in polls
                if isinstance(p.get("id"), int) and p["id"] not in ingested_ids
            ]

        # Optional date floor — read inside discover() so tests can monkeypatch per-call.
        aw_poll_since = os.getenv("AW_POLL_SINCE", "").strip()
        if aw_poll_since:
            # Plain string compare is valid for zero-padded YYYY-MM-DD dates.
            # Polls with a missing/empty field_poll_date are excluded when the floor is set.
            polls = [
                p for p in polls
                if (p.get("field_poll_date") or "") >= aw_poll_since
                and (p.get("field_poll_date") or "") != ""
            ]

        # Sort ASCENDING BY INTEGER POLL ID (not by field_poll_date) for a stable,
        # deterministic batch order. run.py processes the first batch_size ids per run;
        # on the next run those are ingested and drop out of the set-difference, so newer
        # polls surface. Sorting by date could reorder the batch window run-to-run.
        polls_sorted = sorted(polls, key=lambda p: (p.get("id") or 0))
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
        Calls corpus_mapper.chunk_poll() with a minimal source-item stub and
        stamps external_id=poll_id (raw int, no "aw_poll:" prefix).

        Zero-tally guard:
            If the poll produces zero usable fraction tallies (all votes have
            fraction=[]), raises ValueError so run_connector skip-and-continue
            applies.

        Args:
            raw: Dict with keys "poll" (poll item dict) and "votes" (list).

        Returns:
            list[ChunkRecord] — one or more chunks from chunk_poll(), each
            with external_id = poll_id (raw int).

        Raises:
            ValueError: If the poll has zero usable fraction tallies.
        """
        poll: dict = raw["poll"]
        votes: list[dict] = raw["votes"]

        poll_id: int = poll["id"]

        # Zero-tally guard — skip degenerate polls
        tallies = aggregate_fraction_tallies(votes)
        if not tallies:
            raise ValueError(
                f"AW poll {poll_id} has zero usable tallies — "
                "all votes have fraction=[] or no votes at all. "
                "Skipping poll (T-04-13 zero usable tallies)."
            )

        # Build a minimal source-item stub to feed corpus_mapper.chunk_poll().
        # SourceItemRecord is deleted; we use a simple object exposing
        # the five attributes that chunk_poll() reads from the source_item arg.
        poll_date_str: str = poll.get("field_poll_date") or ""
        try:
            publish_date = date_type.fromisoformat(poll_date_str)
        except (ValueError, TypeError):
            # skip-and-warn instead of fabricating date.today().
            # A missing/unparseable poll date makes the publish_date non-deterministic;
            # raising ValueError here triggers run_connector skip-and-continue.
            raise ValueError(
                f"AW poll {poll_id} has missing or unparseable field_poll_date "
                f"{poll_date_str!r} — skipping to avoid fabricated publish_date."
            )

        # external_id_str for UUID determinism (raw integer, no prefix)
        external_id_str = str(poll_id)
        source_item_id = compute_source_item_id("vote_record", external_id_str)

        class _SourceItemStub:
            """Minimal duck-typed stub for chunk_poll (SourceItemLike protocol)."""
            pass

        stub = _SourceItemStub()
        stub.source_item_id = source_item_id  # type: ignore[attr-defined]
        stub.region = self._region  # type: ignore[attr-defined]  # from LegislatureConfig
        stub.authority_tier = AuthorityTier.FACTUAL_RECORD  # type: ignore[attr-defined]
        stub.source_type = SourceType.VOTE_RECORD  # type: ignore[attr-defined]
        stub.publish_date = publish_date  # type: ignore[attr-defined]

        # chunk_poll produces one ChunkRecord per fraction tally.
        chunks = corpus_mapper.chunk_poll(stub, raw)  # type: ignore[arg-type]

        # Derive topic labels for taxonomy lookup.
        # Mirrors corpus.py lines 262-266 field_topics extraction exactly.
        # isinstance check + str() cast before lookup (ASVS V5 — untrusted AW payload).
        # Unknown labels / empty list → ALL_LEVELS + loud logger.warning (inside helper).
        topic_labels: list[str] = [
            str(t["label"])
            for t in (poll.get("field_topics") or [])
            if isinstance(t, dict) and t.get("label")
        ]
        relevance_levels = get_relevance_levels(topic_labels)

        # Stamp external_id, wahlperiode (Bundestag only), region, legislature_period_id,
        # and relevance_levels.
        # ChunkRecord is frozen; use model_copy(update=...) to create new instances.
        # region from LegislatureConfig (replaces hardcoded "DE")
        # legislature_period_id = AW parliament_period ID (globally unique; no collision)
        # wahlperiode stays None for Landtage — state Wahlperiode ints collide
        #            across states (Bayern 8th ≠ NRW 8th in meaning).
        wp = _LEGISLATURE_TO_WAHLPERIODE.get(self._legislature_id)  # None for Landtage
        stamped = [
            chunk.model_copy(update={
                "external_id": poll_id,
                "wahlperiode": wp,                        # None for Landtage
                "region": self._region,                   # from LegislatureConfig.region
                "legislature_period_id": self._period_id, # from LegislatureConfig
                "relevance_levels": relevance_levels,
            })
            for chunk in chunks
        ]
        return stamped

# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
OpenParliamentTvConnector — live incremental connector for openparliament.tv.

Coexist layer alongside ``bundestag_speeches`` (DIP): produces the SAME
``source_type = "parliamentary_speech"`` chunks but with ``source = "op"`` (the
discriminator) plus a timed ``sentence_map`` and a video deep-link payload.
The runner (run.py) owns embed + upsert; this connector is a pure data-transform.

Design (mirrors bundestag_speeches/connector.py, session-granular):
    discover(since) → fetch → normalize → [runner embeds + upserts]

The cursor (``since``) is a YYYYMMDD integer derived by the runner from Qdrant
max(external_id) for ``parliamentary_speech`` + ``source="op"`` (a source-scoped
cursor). ``discover`` floors the enumerated session files at
``since − LOOKBACK_DAYS`` so a session that only *just* aligned BELOW
the prior cursor is re-picked instead of being stranded forever — the runner's
already-present + ``content_hash`` guard makes the re-scan cheap.

Security / robustness:
    - Keyless GitHub-bulk path: NO API-key guard (unlike DIP's _require_dip_key).
    - ``fetch`` never raises: a missing session returns a ``skip_reason`` dict.
    - ``normalize`` raises ``ValueError`` on a skip_reason or a session that yields
      zero usable (aligned + proceedings) speeches → runner skip-and-warn; the
      cursor does NOT advance past a skipped session (idempotent upsert re-processes
      once the session later aligns).
    - Source-supplied media URIs (video/audio/sourcePage) are stored as strings and
      NEVER fetched during ingest; only OpTvClient (pinned host) performs I/O.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from src.ingestion.connector import BaseConnector
from src.ingestion.connectors.bundestag_speeches.constants import MDB_STAMMDATEN_FILE
from src.ingestion.connectors.bundestag_speeches.mdb import load_mdb_lookup
from src.ingestion.connectors.openparliament_tv.client import OpTvClient
from src.ingestion.connectors.openparliament_tv.mappers.corpus import build_chunk_records
from src.ingestion.connectors.openparliament_tv.supersede import supersede_dip_duplicates
from src.ingestion.schemas import ChunkRecord, SourceType

# Shared speech-dedup helpers — one definition for both speech connectors.
from src.ingestion.speech_dedup import datum_to_external_id as _datum_to_external_id
from src.ingestion.speech_dedup import lookback_floor as _lookback_floor

logger = logging.getLogger(__name__)

# MdB-Stammdaten XML, resolved relative to ai-backend/. connector.py is 4 levels
# deep: src/ingestion/connectors/openparliament_tv/connector.py → parents[4] = ai-backend/.
_MDB_PATH: Path = Path(__file__).resolve().parents[4] / MDB_STAMMDATEN_FILE


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _session_external_id(items: list[dict]) -> Optional[int]:
    """Derive a session's YYYYMMDD external_id from the earliest item ``dateStart``."""
    ext_ids = [
        e
        for e in (_datum_to_external_id(it.get("dateStart")) for it in items if isinstance(it, dict))
        if e is not None
    ]
    return min(ext_ids) if ext_ids else None


# ---------------------------------------------------------------------------
# OpenParliamentTvConnector
# ---------------------------------------------------------------------------


class OpenParliamentTvConnector(BaseConnector):
    """Connector for openparliament.tv plenary speeches → parliamentary_speech chunks.

    Session-granular live incremental connector:
        discover(since) → fetch(session_id) → normalize → [runner embeds + upserts]

    Class attributes drive the runner's source-scoped cursor (get_cursor): the
    ``source_type`` matches DIP (``parliamentary_speech``) but ``source = "op"`` keeps
    the op and DIP cursors independent.
    """

    # Used by runner.get_cursor() to scope the Qdrant scroll — SAME as DIP.
    source_type: str = SourceType.PARLIAMENTARY_SPEECH.value

    # Connector discriminator: op and DIP do NOT share one
    # parliamentary_speech cursor, and the op supersede-delete hook stays op-gated.
    source: str = "op"

    def __init__(self, sleep: float = 0.2) -> None:
        self._client = OpTvClient(sleep=sleep)
        # Per-run caches: populated in discover(), read in fetch().
        # basename(str) → {"items": list[raw item], "basename": str, "ext": int}
        self._sessions: dict[str, dict] = {}
        # MdB-Stammdaten lookup loaded once per run in discover().
        self._mdb_lookup: Optional[dict] = None

    # ------------------------------------------------------------------
    # 1. discover — enumerate WP20+21 session files; floor at since − LOOKBACK
    # ------------------------------------------------------------------

    def discover(self, since: Optional[int]) -> list[str]:
        """Return unique session basenames to process, floored at the lookback.

        Enumerates the bulk ``processed/*-session.json`` basenames via the client
        and iterates them in DESCENDING date order, stopping the per-file fetches
        as soon as a fetched session's derived YYYYMMDD external_id drops below
        the ``since − LOOKBACK_DAYS`` floor. Without this early stop EVERY WP20+21
        session JSON (~260+ multi-MB files, paced) would be fetched on each
        incremental run — defeating the cursor and the 15-min job posture.

        Descending-order invariant: the validated basename shape is
        ``{EP:2}{session:03}-session.json`` (SESSION_FILE_RE — e.g. ``20101`` =
        EP 20, session 101). Session numbers are assigned chronologically within
        an electoral period and zero-padded to three digits, so LEXICAL basename
        order is monotone in the session date that ``_session_external_id``
        derives from the earliest item ``dateStart`` — reverse-sorting the
        basenames walks sessions newest-first.

        ``since=None`` (full backfill) fetches ALL sessions — no floor, no early
        stop. Handles are the basenames themselves: unique per session even when
        two sessions share one calendar date. The stamped chunk external_id is
        unaffected — normalize() derives YYYYMMDD per item from ``dateStart``.

        Args:
            since: Max op external_id (YYYYMMDD) already committed to Qdrant for
                   ``parliamentary_speech``/``source="op"``, or None on first run.

        Returns:
            Session basename strings sorted ascending by (YYYYMMDD ext, name) so
            cursor order stays oldest-first.
        """
        # De-duplicate + reverse-sort: newest session file first (see invariant above).
        entries = sorted({str(e) for e in self._client.list_session_files()}, reverse=True)
        floor = _lookback_floor(since) if since is not None else None

        # Tolerate instances built via object.__new__ (unit tests bypass __init__).
        if getattr(self, "_mdb_lookup", None) is None:
            self._mdb_lookup = load_mdb_lookup(_MDB_PATH)

        self._sessions = {}
        discovered: list[tuple[int, str]] = []

        for name in entries:
            try:
                session = self._client.fetch_session_json(name)
            except Exception as exc:  # noqa: BLE001 — a bad session file must not abort the run
                logger.warning("op discover: fetch failed for %s (%s) — skipping.", name, exc)
                continue

            items = [it for it in (session.get("data") or []) if isinstance(it, dict)]
            ext = _session_external_id(items)
            if ext is None:
                continue
            if floor is not None and ext < floor:
                # Descending scan: every remaining basename is older still —
                # stop fetching entirely.
                break
            self._sessions[name] = {"items": items, "basename": name, "ext": ext}
            discovered.append((ext, name))

        return [handle for _ext, handle in sorted(discovered)]

    # ------------------------------------------------------------------
    # 2. fetch — read from cache; never raises (returns skip_reason on miss)
    # ------------------------------------------------------------------

    def fetch(self, external_id: str) -> dict:
        """Return the cached raw session items for one session handle.

        Never raises: a cache miss or a fetch failure returns a ``skip_reason`` dict
        that ``normalize`` converts into a ValueError-skip.

        Args:
            external_id: Session basename string returned by discover()
                         (e.g. ``"20101-session.json"``).

        Returns:
            ``{"external_id", "items", "mdb_lookup"}`` or ``{"skip_reason": ...}``.
        """
        cached = self._sessions.get(str(external_id))
        if cached is None:
            return {"skip_reason": f"op session {external_id} not in discover cache"}

        items = cached.get("items") or []
        basename = cached.get("basename")
        if not items and basename:
            try:
                session = self._client.fetch_session_json(basename)
            except Exception as exc:  # noqa: BLE001 — skip-and-warn, never abort
                return {"skip_reason": f"op session {external_id} fetch failed: {exc}"}
            items = [it for it in (session.get("data") or []) if isinstance(it, dict)]

        return {
            "external_id": external_id,
            "items": items,
            "mdb_lookup": self._mdb_lookup,
        }

    # ------------------------------------------------------------------
    # 3. normalize — build ChunkRecords; alignment gate; stamp YYYYMMDD external_id
    # ------------------------------------------------------------------

    def normalize(self, raw: dict) -> list[ChunkRecord]:
        """Build ChunkRecords from a fetched session; stamp YYYYMMDD external_id + wp.

        Skip-and-warn contract:
            - a ``skip_reason`` key → immediate ValueError;
            - a session that yields zero usable (aligned + proceedings) speeches →
              ValueError so the runner skip-and-continues and the cursor does
              NOT advance past the un-aligned session.

        Each usable speech becomes one whole-speech chunk stamped with
        ``external_id = YYYYMMDD(dateStart)`` and ``wahlperiode = electoralPeriod.number``.

        Args:
            raw: fetch() payload with ``items`` (raw op speech items) + ``mdb_lookup``.

        Raises:
            ValueError: on a skip_reason or a zero-usable-speech session.
        """
        if raw.get("skip_reason"):
            raise ValueError(raw["skip_reason"])

        items: list[dict] = raw.get("items") or []
        mdb_lookup: Optional[dict] = raw.get("mdb_lookup")

        records: list[ChunkRecord] = []
        for item in items:
            recs = build_chunk_records(item, mdb_lookup)
            if not recs:
                # Unaligned / ASR-only / empty-text item — skip.
                continue
            ext = _datum_to_external_id(item.get("dateStart"))
            ep = (item.get("electoralPeriod") or {}).get("number")
            wahlperiode = int(ep) if ep is not None else None
            records.extend(
                rec.model_copy(update={"external_id": ext, "wahlperiode": wahlperiode})
                for rec in recs
            )

        if not records:
            raise ValueError(
                f"op session {raw.get('external_id')}: zero usable aligned+proceedings "
                "speeches (all unaligned, ASR-only, or empty)"
            )

        return records

    # ------------------------------------------------------------------
    # 4. post_upsert — op-owned supersede policy
    # ------------------------------------------------------------------

    def post_upsert(self, qdrant: Any, collection_name: str, chunks: list[ChunkRecord]) -> int:
        """Supersede the just-upserted op speeches' DIP twins.

        Called by run_connector after each successful item upsert. Grafts each
        matched DIP twin's transcript PDF onto the op record, then deletes the
        twin. The policy lives here (connector-owned), not in the generic
        runner; ``supersede_dip_duplicates`` keeps its own op source-gate.

        Returns:
            Number of DIP twins superseded.
        """
        return supersede_dip_duplicates(qdrant, collection_name, chunks, connector=self)

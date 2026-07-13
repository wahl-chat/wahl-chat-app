# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
OpenParliamentTvConnector — live incremental connector for openparliament.tv.

Coexist layer alongside ``bundestag_speeches`` (DIP): produces the SAME
``source_type = "parliamentary_speech"`` chunks but with ``source = "op"`` (the
D-11 discriminator) plus a timed ``sentence_map`` and a video deep-link payload.
The runner (run.py) owns embed + upsert; this connector is a pure data-transform.

Design (mirrors bundestag_speeches/connector.py, session-granular):
    discover(since) → fetch → normalize → [runner embeds + upserts]

The cursor (``since``) is a YYYYMMDD integer derived by the runner from Qdrant
max(external_id) for ``parliamentary_speech`` + ``source="op"`` (a source-scoped
cursor, D-11). ``discover`` floors the enumerated session files at
``since − LOOKBACK_DAYS`` (D-08 / Q3) so a session that only *just* aligned BELOW
the prior cursor is re-picked instead of being stranded forever — the runner's
already-present + ``content_hash`` guard makes the re-scan cheap.

Security / robustness:
    - Keyless GitHub-bulk path: NO API-key guard (unlike DIP's _require_dip_key).
    - ``fetch`` never raises: a missing session returns a ``skip_reason`` dict.
    - ``normalize`` raises ``ValueError`` on a skip_reason or a session that yields
      zero usable (aligned + proceedings) speeches → runner skip-and-warn; the
      cursor does NOT advance past a skipped session (idempotent upsert re-processes
      once the session later aligns, D-03).
    - Source-supplied media URIs (video/audio/sourcePage) are stored as strings and
      NEVER fetched during ingest; only OpTvClient (pinned host) performs I/O.
"""

from __future__ import annotations

import logging
from datetime import date as date_type
from datetime import timedelta
from pathlib import Path
from typing import Any, Optional

from src.ingestion.connector import BaseConnector
from src.ingestion.connectors.bundestag_speeches.constants import MDB_STAMMDATEN_FILE
from src.ingestion.connectors.bundestag_speeches.mdb import load_mdb_lookup
from src.ingestion.connectors.openparliament_tv.client import OpTvClient
from src.ingestion.connectors.openparliament_tv.constants import LOOKBACK_DAYS
from src.ingestion.connectors.openparliament_tv.mappers.corpus import build_chunk_records
from src.ingestion.schemas import ChunkRecord, SourceType

logger = logging.getLogger(__name__)

# MdB-Stammdaten XML, resolved relative to ai-backend/. connector.py is 4 levels
# deep: src/ingestion/connectors/openparliament_tv/connector.py → parents[4] = ai-backend/.
_MDB_PATH: Path = Path(__file__).resolve().parents[4] / MDB_STAMMDATEN_FILE


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _as_external_id(entry: Any) -> Optional[int]:
    """Return a YYYYMMDD external_id int for an already-date-keyed session entry.

    The op bulk client currently enumerates ``YYYYY-session.json`` basenames (an
    EP+session id, not a date), so those return ``None`` here and are resolved by
    fetching the session in ``discover``. A client (or the test fake) that returns
    date-derived external_ids directly is floored without a fetch.
    """
    if isinstance(entry, bool):  # bool is an int subclass — reject explicitly
        return None
    if isinstance(entry, int):
        return entry
    if isinstance(entry, str) and entry.isdigit():
        return int(entry)
    return None


def _lookback_floor(since: int) -> int:
    """Translate a YYYYMMDD cursor into a ``since − LOOKBACK_DAYS`` YYYYMMDD floor."""
    s = str(since)
    try:
        cursor_date = date_type(int(s[0:4]), int(s[4:6]), int(s[6:8]))
    except (ValueError, IndexError):
        return since
    floored = cursor_date - timedelta(days=LOOKBACK_DAYS)
    return int(floored.strftime("%Y%m%d"))


def _datum_to_external_id(date_start: Optional[str]) -> Optional[int]:
    """Convert an op ISO ``dateStart`` (e.g. ``2023-04-28T10:12:00+02:00``) to YYYYMMDD."""
    iso = str(date_start or "")[:10]
    try:
        return int(iso.replace("-", ""))
    except ValueError:
        return None


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
    the op and DIP cursors independent (D-11).
    """

    # Used by runner.get_cursor() to scope the Qdrant scroll — SAME as DIP.
    source_type: str = SourceType.PARLIAMENTARY_SPEECH.value

    # NEW connector discriminator (D-11): op and DIP do NOT share one
    # parliamentary_speech cursor, and the op supersede-delete hook stays op-gated.
    source: str = "op"

    def __init__(self, sleep: float = 0.2) -> None:
        self._client = OpTvClient(sleep=sleep)
        # Per-run caches: populated in discover(), read in fetch().
        # external_id(str) → {"items": list[raw item], "basename": Optional[str]}
        self._sessions: dict[str, dict] = {}
        # MdB-Stammdaten lookup loaded once per run in discover().
        self._mdb_lookup: Optional[dict] = None

    # ------------------------------------------------------------------
    # 1. discover — enumerate WP20+21 session files; floor at since − LOOKBACK
    # ------------------------------------------------------------------

    def discover(self, since: Optional[int]) -> list[str]:
        """Return unique session HANDLES to process, floored at the lookback.

        Enumerates the bulk ``processed/*-session.json`` files via the client, floors
        the scan at ``since − LOOKBACK_DAYS`` (D-08/Q3), populates the per-run cache
        of raw speech items keyed by a UNIQUE session handle, and loads the MdB
        lookup once.

        Handle disambiguation: two sessions whose earliest ``dateStart`` falls on
        the SAME calendar date previously collided on the ``str(ext)`` cache key,
        silently dropping one session's speeches. The DISCOVER/CACHE handle is now
        unique per session — the file basename when present, or (direct-ext fast
        path with no basename) ``"{ext}"`` with a run-local ``#{n}`` suffix on
        collision. The stamped chunk external_id is UNAFFECTED: normalize()
        derives the YYYYMMDD external_id per item from ``dateStart``, so the
        cursor order_by stays an int.

        Args:
            since: Max op external_id (YYYYMMDD) already committed to Qdrant for
                   ``parliamentary_speech``/``source="op"``, or None on first run.

        Returns:
            Session handle strings sorted ascending by (YYYYMMDD ext, handle) so
            cursor order stays oldest-first.
        """
        entries = list(self._client.list_session_files())
        floor = _lookback_floor(since) if since is not None else None

        # Tolerate instances built via object.__new__ (unit tests bypass __init__).
        if getattr(self, "_mdb_lookup", None) is None:
            self._mdb_lookup = load_mdb_lookup(_MDB_PATH)

        self._sessions = {}
        discovered: list[tuple[int, str]] = []
        direct_seen: dict[int, int] = {}

        for entry in entries:
            direct_ext = _as_external_id(entry)
            if direct_ext is not None:
                # Client already yields a date-keyed session external_id — floor
                # without fetching (fast path; also the test-fake contract).
                if floor is not None and direct_ext < floor:
                    continue
                # No basename available — disambiguate same-date entries with a
                # run-local monotonic suffix so neither overwrites the other.
                n = direct_seen.get(direct_ext, 0)
                direct_seen[direct_ext] = n + 1
                handle = str(direct_ext) if n == 0 else f"{direct_ext}#{n}"
                self._sessions[handle] = {
                    "items": [],
                    "basename": None,
                    "ext": direct_ext,
                }
                discovered.append((direct_ext, handle))
                continue

            # Basename path: fetch + derive the session's date-based external_id, floor.
            name = str(entry)
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
                continue
            if name in self._sessions:
                continue  # duplicate enumeration of the same session file
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
            external_id: Unique session handle string returned by discover()
                         (basename, or YYYYMMDD ext with optional ``#{n}`` suffix).

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
    # 3. normalize — build ChunkRecords; D-03 gate; stamp YYYYMMDD external_id
    # ------------------------------------------------------------------

    def normalize(self, raw: dict) -> list[ChunkRecord]:
        """Build ChunkRecords from a fetched session; stamp YYYYMMDD external_id + wp.

        Skip-and-warn contract:
            - a ``skip_reason`` key → immediate ValueError;
            - a session that yields zero usable (aligned + proceedings) speeches →
              ValueError (D-03) so the runner skip-and-continues and the cursor does
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
                # Unaligned / ASR-only / empty-text item — D-03 skip.
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

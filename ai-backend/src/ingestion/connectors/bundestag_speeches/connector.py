# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
BundestagSpeechesConnector — live incremental connector.

This connector implements the 3-method
synchronous ABC (discover/fetch/normalize) and produces list[ChunkRecord]
directly from normalize() — no Firestore, no GCS, no work_queue.

The runner (run.py) owns embed + upsert; this connector is pure data-transform.
The cursor (since) is a YYYYMMDD integer derived by the runner from Qdrant
max(external_id) for "parliamentary_speech" — passed to discover() as the date
floor.  No watermark methods needed.

Security notes:
    DIP_API_KEY fail-loud: _require_dip_key() raises RuntimeError
    at construction when DIP_API_KEY is unset.  NO hardcoded key.

    DESC → ASC re-sort: DIP returns protocols newest-first.
    discover() re-sorts ascending by (datum, id) so run_connector processes
    oldest-first and the YYYYMMDD cursor advances monotonically.

    fetch() never raises: missing xml_url / parse failures return a
    skip_reason dict; normalize() raises ValueError → runner skip-and-warn.
    The cursor does NOT advance past skipped protocols (idempotent upsert
    handles re-processing if a protocol later becomes available).

    DIP XML fetched via absorbed fetch_text/defusedxml; the
    xml_url comes only from DIP responses, never from caller input.

CONCURRENCY HAZARD:
    The DIP and openparliament_tv schedules MUST be serialized — never run both
    connectors concurrently. The interleaving "DIP resurrection-guard passes →
    op ingests + supersedes → DIP commits" can strand a DIP twin that no later
    run's new-chunk/orphan filters ever cover. As a cheap self-heal, normalize()
    records the siids it SKIPPED as op-superseded in ``last_superseded_siids``;
    run_connector deletes any stored points under them on the next (serialized)
    DIP run.
"""

from __future__ import annotations

import difflib
import logging
import os
from pathlib import Path
from typing import Any, Optional

from src.ingestion.connector import BaseConnector
from src.ingestion.connectors.bundestag_speeches.client import DipClient, fetch_text
from src.ingestion.connectors.bundestag_speeches.constants import MDB_STAMMDATEN_FILE
from src.ingestion.connectors.bundestag_speeches.mappers import corpus as corpus_mapper
from src.ingestion.connectors.bundestag_speeches.mdb import (
    ensure_mdb_lookup,
    mdb_party_for_speech,
    mdb_record_for_speaker_name,
)
from src.ingestion.connectors.bundestag_speeches.parser import parse_speeches_from_xml
from src.ingestion.connectors.bundestag_speeches.utils import normalize_party
from src.ingestion.ids import compute_source_item_id
from src.ingestion.schemas import ChunkRecord, SourceType
from src.ingestion.setup_collection import COLLECTION_NAME

# Shared speech-dedup helpers — one definition for both speech connectors
# and the op supersede module; drift between copies would silently break
# cross-source dedup.
from src.ingestion.speech_dedup import (
    LOOKBACK_DAYS,  # noqa: F401 — re-export: docstrings/operators reference it here
    RESURRECTION_TEXT_MATCH_RATIO as _RESURRECTION_TEXT_MATCH_RATIO,
)
from src.ingestion.speech_dedup import datum_to_external_id as _datum_to_external_id
from src.ingestion.speech_dedup import lookback_floor as _lookback_floor
from src.ingestion.speech_dedup import norm_speech_text as _norm_speech_text

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level path for MdB-Stammdaten XML
# ---------------------------------------------------------------------------

# Resolved relative to the ai-backend/ directory (connector.py is 4 levels deep:
# src/ingestion/connectors/bundestag_speeches/connector.py → parents[4] = ai-backend/)
_MDB_PATH: Path = Path(__file__).resolve().parents[4] / MDB_STAMMDATEN_FILE


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _require_dip_key() -> str:
    """Read DIP_API_KEY from env; raise RuntimeError when unset.

    No hardcoded default key — published keys expire. The caller MUST
    supply a fresh key via DIP_API_KEY in .env (local dev) or the Cloud Run Job
    environment.

    Returns:
        The DIP API key string.

    Raises:
        RuntimeError: When DIP_API_KEY is not set in the environment.
    """
    key = os.getenv("DIP_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "DIP_API_KEY not set. "
            "Fetch the current public key from "
            "https://dip.bundestag.de/über-dip/hilfe/api "
            "and add it to ai-backend/.env as DIP_API_KEY=<key>."
        )
    return key


# LOOKBACK_DAYS and _lookback_floor are imported from src/ingestion/speech_dedup.py
# above. run.py's batch budget ensures already-present protocols inside the
# window do not stall the batch.


def _yyyymmdd_int_to_iso(since: int) -> str:
    """Convert a YYYYMMDD integer cursor to an ISO date string.

    Args:
        since: Integer cursor e.g. 20260615.

    Returns:
        ISO date string e.g. "2026-06-15".
    """
    s = str(since)
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"


def _is_non_mdb_speaker(speech: dict) -> bool:
    """Return True when the speaker_xml_id is in the non-MdB 999… range.

    These are parliamentary officials (Präsident/Vizepräsident etc.) who are
    not party members; their 999… IDs are not in the MdB-Stammdaten and their
    speeches are typically not party-attributed content.

    Args:
        speech: Speech dict from parse_speeches_from_xml.

    Returns:
        True when the ID starts with "999", False otherwise.
    """
    person_id = speech.get("speaker_xml_id") or ""
    return str(person_id).startswith("999")


# A DIP speech is treated as op-superseded only when an op speech under the SAME
# speech_key has matching text at/above _RESURRECTION_TEXT_MATCH_RATIO (shared
# constant, speech_dedup.py). speech_key is not unique per speech, so a
# bare "an op owns this key" test would skip a DISTINCT DIP speech a speaker
# gave under the same agenda item that op never aligned. Same speech across
# op/DIP scores ~0.99; a different speech scores far lower.


def is_op_superseded(
    qdrant: Any,
    collection_name: str,
    speech_key: Optional[str],
    dip_text: Optional[str] = None,
) -> bool:
    """Return True when op has already ingested THIS speech.

    The DIP connector consults this BEFORE inserting a speech: if op already holds
    the SAME speech, the DIP duplicate must NOT be (re)inserted — even during a
    full backfill / cursor reset (``since=None``). Because it keys on the STORED op
    chunk rather than the incremental cursor, a cursor reset cannot resurrect the
    op-superseded DIP duplicate.

    Precise match: ``speech_key`` is NOT unique per speech, so "an op
    owns this key" is not enough — a speaker's second turn under the same agenda
    item shares the key but is a DISTINCT speech op may never have aligned.
    When ``dip_text`` is given we scroll the op speeches under the key and treat
    this DIP speech as superseded ONLY if some op speech's full text matches it
    (``ratio >= _RESURRECTION_TEXT_MATCH_RATIO``). A ``dip_text`` that folds to
    EMPTY after normalization is unverifiable — return False (insert; fail-safe)
    rather than trusting bare key existence. Without ``dip_text`` (None)
    the guard falls back to the coarse "any op under the key" test.

    Fail-safe: when Qdrant is unreachable / the scroll raises, return
    False (do NOT skip → insert) so a transient outage cannot abort the run; the
    op supersede + retrieval prefer-op dedup still collapse any transient dup.

    Returns:
        True when op already holds this speech (skip insert), else False.
    """
    if not speech_key:
        return False
    try:
        from qdrant_client import models  # noqa: PLC0415

        op_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="speech_key", match=models.MatchValue(value=speech_key)
                ),
                models.FieldCondition(
                    key="source", match=models.MatchValue(value="op")
                ),
            ]
        )
        if dip_text is None:
            # Coarse legacy path: existence check only.
            points, _ = qdrant.scroll(
                collection_name=collection_name,
                scroll_filter=op_filter,
                limit=1,
                with_payload=False,
                with_vectors=False,
            )
            return bool(points)

        # Precise path: collect op speeches (full text by source_item_id) under
        # the key. chunk_index is fetched so a multi-chunk speech joins in chunk
        # order, not scroll order — an out-of-order "B+A" concatenation
        # would score ~0.5 against the DIP "A+B" and silently miss the match.
        op_texts: dict[Any, list] = {}
        offset = None
        while True:
            points, offset = qdrant.scroll(
                collection_name=collection_name,
                scroll_filter=op_filter,
                limit=256,
                offset=offset,
                with_payload=["source_item_id", "text", "chunk_index"],
                with_vectors=False,
            )
            for point in points:
                payload = point.payload or {}
                op_texts.setdefault(payload.get("source_item_id"), []).append(
                    (payload.get("chunk_index") or 0, payload.get("text") or "")
                )
            if offset is None:
                break
    except Exception as exc:  # noqa: BLE001 — Qdrant unreachable → fail-safe insert
        logger.warning(
            "resurrection guard: Qdrant consult failed for speech_key %r (%s) — "
            "inserting (fail-safe)",
            speech_key,
            exc,
        )
        return False

    if not op_texts:
        return False
    dip_norm = _norm_speech_text(dip_text)
    if not dip_norm:
        # No comparable text → cannot verify it is the SAME speech; fail safe
        # and insert: a bare "an op holds the key" existence test would
        # skip a DISTINCT same-key DIP speech, consistent with the fail-safe
        # posture everywhere else in this guard. The op supersede pass and the
        # query-time prefer-op dedup collapse any transient duplicate.
        return False
    for texts in op_texts.values():
        # Join in chunk_index order, never scroll order.
        op_norm = _norm_speech_text(
            " ".join(t for _idx, t in sorted(texts, key=lambda pair: pair[0]))
        )
        if op_norm and difflib.SequenceMatcher(None, dip_norm, op_norm).ratio() >= (
            _RESURRECTION_TEXT_MATCH_RATIO
        ):
            return True
    return False


def _build_speech_row(
    protocol: dict,
    speech: dict,
    mdb_lookup: dict,
) -> dict:
    """Build a speech row dict suitable for corpus_mapper.build_chunk_records.

    Party resolution order:
      1. normalize_party(speech['party']) — from XML <fraktion>
      2. mdb_party_for_speech(speech, mdb_lookup) — MdB-Stammdaten fallback

    person_id override:
      If mdb_record_for_speaker_name resolves to a different non-empty id,
      use the MdB record id.

    Args:
        protocol: Protocol metadata dict from DIP (keys: id, datum, wahlperiode, fundstelle).
        speech:   Speech dict from parse_speeches_from_xml.
        mdb_lookup: MdB-Stammdaten lookup built once in discover().

    Returns:
        Dict compatible with corpus_mapper.build_chunk_records input contract.
    """
    # --- party resolution ---
    # Track whether party came from the XML <fraktion> tag or MdB-Stammdaten fallback.
    # The CSU refinement (below) runs ONLY for the fraktion path — if party already
    # came from MdB, it's already the speaker's true party and must not be re-refined.
    party = normalize_party(speech.get("party"))
    party_from_fraktion = party is not None
    if not party:
        party = mdb_party_for_speech(speech, mdb_lookup)

    # --- CSU disambiguation (Union/cdu fraktion → per-speaker csu refinement) ---
    # When the XML <fraktion> resolved to the joint Union label (slug "cdu"), the
    # speaker may individually be a CSU member.  Consult the already-loaded MdB
    # lookup for THIS speaker and refine cdu → csu only when:
    #   (a) party came from the XML <fraktion> (not from MdB fallback)
    #   (b) the fraktion slug is exactly "cdu" (Union family)
    #   (c) the per-speaker MdB entry resolves to slug "csu"
    # Any other party (SPD, AfD, etc.) is never touched by this block.
    if (
        party_from_fraktion
        and party is not None
        and corpus_mapper.party_to_slug(party) == "cdu"
    ):
        mdb_party = mdb_party_for_speech(speech, mdb_lookup)
        if mdb_party is not None and corpus_mapper.party_to_slug(mdb_party) == "csu":
            party = mdb_party

    # --- person_id override ---
    person_id = speech.get("speaker_xml_id")
    mdb_record = mdb_record_for_speaker_name(speech, mdb_lookup)
    if mdb_record and mdb_record.get("id") and mdb_record["id"] != person_id:
        person_id = mdb_record["id"]

    # --- protocol metadata ---
    # protocol_id is the human "Wahlperiode/Sitzung" dokumentnummer (e.g. "20/101").
    # The shared speech_key derives the session number from it (session =
    # protocol_id.split("/")[1]) for parity with op's session.number — so it MUST be
    # the "wp/session" form, not the internal DIP document id. Fall back to the
    # internal id only when the dokumentnummer is absent. protocol_api_id keeps the
    # internal DIP document id for API lookups.
    protocol_api_id = str(protocol.get("id") or "")
    dokumentnummer = str(protocol.get("dokumentnummer") or "").strip()
    protocol_id = dokumentnummer or protocol_api_id
    protocol_datum = protocol.get("datum") or ""

    # xml_url from fundstelle (used as citation_url fallback — pdf_url may be absent)
    fundstelle = protocol.get("fundstelle") or {}
    pdf_url = fundstelle.get("pdf_url") or None

    return {
        "id": speech.get("xml_rede_id") or "",
        "text": speech.get("text") or "",
        "date": protocol_datum,
        "party": party,
        "speaker_name": speech.get("speaker_name") or "",
        "protocol_id": protocol_id,
        "protocol_api_id": protocol_api_id,
        "pdf_url": pdf_url,
        "person_id": person_id,
        "xml_rede_id": speech.get("xml_rede_id") or None,
        "wahlperiode": protocol.get("wahlperiode"),
        # Enclosing <tagesordnungspunkt top-id> for the shared agenda-bearing speech_key.
        "agenda_top_id": speech.get("agenda_top_id"),
    }


# ---------------------------------------------------------------------------
# BundestagSpeechesConnector
# ---------------------------------------------------------------------------


class BundestagSpeechesConnector(BaseConnector):
    """Connector for Bundestag plenary speeches → parliamentary_speech ChunkRecords.

    Live incremental connector:
        discover(since) → fetch → normalize → [runner embeds + upserts]

    The cursor (since) is the max external_id (YYYYMMDD integer of the protocol
    date) already committed to Qdrant for "parliamentary_speech", derived by the
    runner via get_cursor().  No Firestore, no GCS, no work queue.

    The connector fetches plenary protocols from the DIP Bundestag API (/plenarprotokoll),
    downloads and parses the XML for each protocol, and returns ChunkRecords with
    party-attributed speech text.

    Args:
        wahlperiode: Bundestag Wahlperiode (legislature period) to scope discovery.
                     Defaults to 21 (21st Bundestag 2025-) or DIP_WAHLPERIODE env.
    """

    # Class attribute: used by runner.get_cursor() to scope the Qdrant scroll.
    source_type: str = SourceType.PARLIAMENTARY_SPEECH.value

    # Connector discriminator: stamps chunks source="dip" and keeps the op
    # supersede hook op-gated (fires only for source="op").
    source: str = "dip"

    # The DIP cursor must NOT be scoped to source="dip". op progressively
    # supersede-DELETES dip points, so max(external_id, source="dip") walks
    # BACKWARD as coverage grows (worst case None → the run re-fetches and
    # re-parses the whole Wahlperiode every time). op external_ids are the same
    # YYYYMMDD scale and op only ever supersedes a dip twin that WAS ingested,
    # so the cross-source max over parliamentary_speech is a valid,
    # non-regressing floor; the lookback window still re-covers recent gaps.
    # (op keeps its own source-scoped cursor via the BaseConnector default.)
    cursor_source = None

    def __init__(
        self,
        wahlperiode: Optional[int] = None,
        qdrant: Optional[Any] = None,
        collection_name: str = COLLECTION_NAME,
    ) -> None:
        # Read DIP_WAHLPERIODE at CALL time, not import time — a default-arg
        # getenv freezes the value when the module is first imported, ignoring
        # any later environment change in the same process.
        if wahlperiode is None:
            wahlperiode = int(os.getenv("DIP_WAHLPERIODE", "21"))
        self._wahlperiode = wahlperiode
        self._client = DipClient(api_key=_require_dip_key())
        # Per-run cache: populated in discover(), read in fetch()
        self._protocols: dict[str, dict] = {}
        # MdB-Stammdaten lookup: loaded once per run in discover(), reused in fetch()/normalize()
        self._mdb_lookup: Optional[dict] = None
        # Resurrection guard: a QdrantClient consulted before inserting each
        # DIP speech. Injectable for tests; lazily built from QDRANT_URL on first use
        # in production. Kept optional so the guard degrades to fail-safe insert when
        # no client can be constructed.
        self._qdrant: Optional[Any] = qdrant
        self._collection_name = collection_name
        # Lazy-build a real QdrantClient from QDRANT_URL only when no client was
        # injected (production path). Instances created without __init__ (unit tests
        # via object.__new__) lack this flag → getattr default False → guard disabled
        # (fail-safe insert), so discover/normalize unit tests issue no Qdrant calls.
        self._qdrant_lazy_enabled: bool = qdrant is None
        # Self-heal: siids normalize() skipped as op-superseded on the LAST
        # item. run_connector deletes any stored points under them (a stranded
        # DIP twin from an interleaved concurrent DIP+op run).
        self.last_superseded_siids: tuple[str, ...] = ()

    def _get_qdrant(self) -> Optional[Any]:
        """Return the QdrantClient for the resurrection guard, lazily constructed.

        Uses an injected client when present (tests). In production, builds a
        QdrantClient from QDRANT_URL once and caches it. Any construction failure
        returns None so the guard degrades to fail-safe insert rather than
        aborting the run.
        """
        qdrant = getattr(self, "_qdrant", None)
        if qdrant is not None:
            return qdrant
        # Only lazy-construct on the production path (__init__ ran with no injected
        # client). Test instances built via object.__new__ lack the flag → no build.
        if not getattr(self, "_qdrant_lazy_enabled", False):
            return None
        try:
            from qdrant_client import QdrantClient  # noqa: PLC0415

            qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
            self._qdrant = QdrantClient(
                url=qdrant_url, api_key=os.getenv("QDRANT_API_KEY")
            )
        except Exception as exc:  # noqa: BLE001 — no client → fail-safe insert
            logger.warning(
                "resurrection guard: could not construct QdrantClient (%s) — "
                "guard disabled (fail-safe insert)",
                exc,
            )
            self._qdrant = None
        return self._qdrant

    # ------------------------------------------------------------------
    # 1. discover — YYYYMMDD cursor → DIP date floor; re-sort ASC
    # ------------------------------------------------------------------

    def discover(self, since: Optional[int]) -> list[str]:
        """Return protocol ids to process for the configured Wahlperiode.

        Queries DIP /plenarprotokoll with f.wahlperiode and (when since is set)
        f.datum.start floored at ``since − LOOKBACK_DAYS`` — an inclusive floor
        at the raw since date would permanently exclude any earlier-dated
        protocol that transiently failed on a prior run (the max external_id
        advanced past it). The lookback keeps API cost bounded (no full WP-history
        walk) while re-discovering recent failures; run.py's batch-budget fix
        ensures already-present protocols inside the window do not stall.
        Walks all cursor-pages.
        Filters to Bundestagsprotokolle (herausgeber == "BT").
        Re-sorts ascending by (datum, id) — DIP returns DESC.
        Populates self._protocols (per-run cache).
        Loads self._mdb_lookup once per run.

        Args:
            since: Max external_id (YYYYMMDD integer) already committed to
                   Qdrant for "parliamentary_speech", or None on first run.
                   Derived by the runner via get_cursor().

        Returns:
            List of protocol id strings sorted ascending by (datum, id).
        """
        floor_int: Optional[int] = _lookback_floor(since) if since is not None else None
        params: dict = {"f.wahlperiode": self._wahlperiode}
        if floor_int is not None:
            params["f.datum.start"] = _yyyymmdd_int_to_iso(floor_int)

        docs: list[dict] = []
        for page in self._client.pages("/plenarprotokoll", params):
            for doc in page.get("documents", []):
                # herausgeber == "BT" filter: skip non-Bundestag protocols (e.g. Bundesrat).
                fundstelle = doc.get("fundstelle") or {}
                herausgeber = (
                    fundstelle.get("herausgeber") or doc.get("herausgeber") or ""
                )
                if herausgeber and herausgeber != "BT":
                    continue
                docs.append(doc)

        # Client-side floor filter: DIP server-side f.datum.start is an optimisation;
        # post-filter here for correctness since the fake client (and early DIP responses)
        # may return protocols before the floor. Uses the SAME lookback-adjusted floor
        # as the server-side param so a failed-below-max protocol is re-discovered.
        if floor_int is not None:
            floor_iso = _yyyymmdd_int_to_iso(floor_int)
            docs = [d for d in docs if (d.get("datum") or "") >= floor_iso]

        # DIP sorts DESC; BaseConnector.discover contract (connector.py L49) wants ASC.
        # Re-sort ascending by (datum, id) so run_connector processes oldest-first.
        docs.sort(key=lambda d: (d.get("datum") or "", str(d.get("id") or "")))

        # Populate per-run cache
        self._protocols = {str(d["id"]): d for d in docs}

        # Load MdB-Stammdaten once per run (cached — never load per-fetch).
        # ensure_* fetches on a cache miss and fails loud if the master data is
        # unavailable, rather than degrading every minister/president to "unbekannt".
        if self._mdb_lookup is None:
            self._mdb_lookup = ensure_mdb_lookup(_MDB_PATH)

        return [str(d["id"]) for d in docs]

    # ------------------------------------------------------------------
    # 2. fetch — read from cache; return skip_reason dict on failure (never raises)
    # ------------------------------------------------------------------

    def fetch(self, external_id: str) -> dict:
        """Fetch and parse the XML for one protocol; return skip_reason on failure.

        Reads from the per-run cache populated by discover().  Never raises
        (all failure modes return a skip_reason dict — normalize() converts
        these to ValueError so run_connector skip-and-warns).

        Args:
            external_id: String protocol id (e.g. "12345").

        Returns:
            Dict with keys:
              - "protocol": the protocol metadata dict (or None)
              - "speeches": list of speech dicts from parse_speeches_from_xml
              - "mdb_lookup": the MdB-Stammdaten lookup dict
            OR a skip_reason dict:
              - "protocol": ..., "speeches": [], "skip_reason": "<reason>"
        """
        protocol = self._protocols.get(external_id)
        if protocol is None:
            return {
                "protocol": None,
                "speeches": [],
                "skip_reason": f"protocol {external_id} not in discover cache",
            }

        fundstelle = protocol.get("fundstelle") or {}
        xml_url = fundstelle.get("xml_url") or ""
        if not xml_url:
            return {
                "protocol": protocol,
                "speeches": [],
                "skip_reason": f"protocol {external_id} has no xml_url",
            }

        try:
            xml_text = fetch_text(xml_url)
            speeches = parse_speeches_from_xml(xml_text)
        except Exception as exc:  # noqa: BLE001 — ParseError/RequestException → skip-and-warn
            return {
                "protocol": protocol,
                "speeches": [],
                "skip_reason": f"xml parse failed for protocol {external_id}: {exc}",
            }

        return {
            "protocol": protocol,
            "speeches": speeches,
            "mdb_lookup": self._mdb_lookup,
        }

    # ------------------------------------------------------------------
    # 3. normalize — build ChunkRecords + stamp external_id=YYYYMMDD
    # ------------------------------------------------------------------

    def normalize(self, raw: dict) -> list[ChunkRecord]:
        """Build ChunkRecords from fetch() payload; stamp YYYYMMDD external_id.

        Skip-and-warn contract:
            - If raw contains a "skip_reason" key, raises ValueError immediately.
            - If the protocol produces zero usable speeches (all dropped),
              raises ValueError so run_connector skip-and-continues — UNLESS ≥1
              speech was skipped as op-superseded and none remain: that is
              a fully-op-covered protocol, returned as [] (clean no-op).

        Party resolution (collector.build_speech_row logic):
            XML <fraktion> → normalize_party → MdB-Stammdaten fallback.
            is_non_mdb_speaker (999…) speakers are dropped.

        External_id stamp:
            Every chunk gets external_id=YYYYMMDD(protocol.datum) via model_copy.
            wahlperiode is also stamped from the protocol metadata.

        Args:
            raw: Dict returned by fetch(), with keys "protocol", "speeches",
                 "mdb_lookup" (and optionally "skip_reason").

        Returns:
            list[ChunkRecord] — one or more chunks, each with external_id=YYYYMMDD.

        Raises:
            ValueError: If raw has a skip_reason, or if zero usable speeches result.
        """
        # skip_reason → ValueError (run_connector catches and warns)
        if raw.get("skip_reason"):
            raise ValueError(raw["skip_reason"])

        protocol: dict = raw["protocol"]
        speeches: list[dict] = raw.get("speeches", [])
        mdb_lookup: dict = raw.get("mdb_lookup") or {"by_id": {}, "by_name": {}}

        # Build speech rows, dropping non-MdB speakers (999…) and empty-text speeches
        rows: list[dict] = []
        for speech in speeches:
            if not speech.get("text"):
                continue
            if _is_non_mdb_speaker(speech):
                continue
            rows.append(_build_speech_row(protocol, speech, mdb_lookup))

        # Durable resurrection guard: before building/inserting a DIP chunk,
        # consult the indexed speech_key and SKIP any speech op has already
        # superseded (an op point with the same speech_key). This runs regardless of
        # the incremental cursor (full backfill / since=None included) so a cursor
        # reset cannot resurrect op-superseded DIP duplicates. Qdrant-unreachable
        # fails safe (is_op_superseded returns False → insert).
        qdrant = self._get_qdrant()

        # Build ChunkRecord list via the relocated mapper. Skipped-as-superseded
        # siids are collected and exposed via last_superseded_siids so the runner
        # can delete a stranded twin from an interleaved concurrent run.
        records: list[ChunkRecord] = []
        superseded_siids: list[str] = []
        for row in rows:
            if qdrant is not None:
                speech_key = corpus_mapper.compute_speech_key(row)
                if speech_key is not None and is_op_superseded(
                    qdrant, self._collection_name, speech_key, dip_text=row.get("text")
                ):
                    logger.info(
                        "resurrection guard: skipping op-superseded DIP speech "
                        "(speech_key=%s)",
                        speech_key,
                    )
                    superseded_siids.append(
                        str(
                            compute_source_item_id(
                                "parliamentary_speech",
                                str(row.get("id") or ""),
                                source="dip",
                            )
                        )
                    )
                    continue
            records.extend(corpus_mapper.build_chunk_records(row))
        # Per-item report (reset every normalize call; () when nothing skipped).
        self.last_superseded_siids = tuple(superseded_siids)

        # Skip-and-warn: zero usable speeches → ValueError. EXCEPTION: when
        # ≥1 speech was skipped as op-superseded and none remain, the protocol is
        # FULLY covered by op — a clean no-op, not an error. Raising here would
        # re-surface the protocol into failed_ids on every run for the whole
        # lookback window (60 days of noise for correct behavior).
        if not records:
            if superseded_siids:
                logger.info(
                    "protocol %s: all usable speeches already op-superseded — clean no-op",
                    (protocol or {}).get("id", "unknown"),
                )
                return []
            protocol_id = (protocol or {}).get("id", "unknown")
            raise ValueError(
                f"protocol {protocol_id} produced zero usable speeches "
                "(all speeches were empty, non-MdB, or had no text)"
            )

        # Stamp external_id = YYYYMMDD(protocol.datum) and wahlperiode on every chunk.
        # ChunkRecord is frozen; use model_copy(update=...) to create new instances.
        datum = (protocol or {}).get("datum") or ""
        external_id = _datum_to_external_id(datum) if datum else None

        raw_wp = (protocol or {}).get("wahlperiode")
        wahlperiode = int(raw_wp) if raw_wp is not None else None

        return [
            chunk.model_copy(
                update={"external_id": external_id, "wahlperiode": wahlperiode}
            )
            for chunk in records
        ]

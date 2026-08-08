# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
BundestagSpeechesConnector — live incremental connector.

This connector implements the 3-method
synchronous ABC (discover/fetch/normalize) and produces list[ChunkRecord]
directly from normalize() — no Firestore, no GCS, no work_queue.

The runner (run.py) owns embed + upsert; this connector is pure data-transform.
The runner still passes its Qdrant-derived cursor to discover() (ABC contract),
but discover() deliberately IGNORES it: discovery is a per-Wahlperiode
SET-DIFFERENCE against the store (protocols in DIP minus protocols with stored
DIP chunks) plus a recent-update sweep over DIP's ``aktualisiert`` timestamp.
A date-floor cursor was order-dependent (openparliament or a newer Wahlperiode
advancing the shared max starved older DIP backfills) and permanently lost
protocols that failed for longer than the lookback window; set-difference
re-surfaces every gap and needs no watermark.

Security notes:
    DIP_API_KEY fail-loud: _require_dip_key() raises RuntimeError
    at construction when DIP_API_KEY is unset.  NO hardcoded key.

    DESC → ASC re-sort: DIP returns protocols newest-first.
    discover() re-sorts ascending by (datum, id) so run_connector processes
    oldest-first.

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
from datetime import date as date_type
from datetime import timedelta
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
from src.ingestion.connectors.bundestag_speeches.pdf_pages import (
    fetch_pdf_reader,
    resolve_page_offset,
)
from src.ingestion.connectors.bundestag_speeches.utils import normalize_party
from src.ingestion.ids import compute_source_item_id
from src.ingestion.schemas import ChunkRecord, SourceType
from src.ingestion.setup_collection import COLLECTION_NAME

# Shared speech-dedup helpers — one definition for both speech connectors
# and the op supersede module; drift between copies would silently break
# cross-source dedup.
from src.ingestion.speech_dedup import (
    RESURRECTION_TEXT_MATCH_RATIO as _RESURRECTION_TEXT_MATCH_RATIO,
)
from src.ingestion.speech_dedup import datum_to_external_id as _datum_to_external_id
from src.ingestion.speech_dedup import norm_speech_text as _norm_speech_text

logger = logging.getLogger(__name__)


def _page_offset_samples(speeches: list[dict], limit: int = 3) -> list[tuple[int, int]]:
    """Up to *limit* (printed page, estimated pdf page) pairs with distinct
    printed pages — the validation samples for ``resolve_page_offset``."""
    samples: list[tuple[int, int]] = []
    seen: set[int] = set()
    for speech in speeches:
        printed = speech.get("source_page")
        estimate = speech.get("pdf_page")
        if (
            isinstance(printed, str)
            and printed.isdigit()
            and isinstance(estimate, int)
            and int(printed) not in seen
        ):
            seen.add(int(printed))
            samples.append((int(printed), estimate))
            if len(samples) >= limit:
                break
    return samples


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


# Recent-update sweep window: protocols whose DIP ``aktualisiert`` timestamp is
# within this many days are re-surfaced even when already ingested, so upstream
# transcript corrections propagate (content_hash makes unchanged ones cheap
# skips). DIP publishes corrections shortly after a sitting; 30 days is well
# beyond the observed correction latency.
_UPDATE_SWEEP_DAYS = 30


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
        # autojunk=False keeps this comparator symmetric with the op supersede
        # pass: the default auto-junk heuristic marks frequent characters as
        # junk on long normalized speech strings and misses real twins.
        if (
            op_norm
            and difflib.SequenceMatcher(None, dip_norm, op_norm, autojunk=False).ratio()
            >= _RESURRECTION_TEXT_MATCH_RATIO
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
        # Citation coordinates from the protocol TOC (parser xref map).
        "source_page": speech.get("source_page"),
        "page_quadrant": speech.get("page_quadrant"),
        "pdf_page": speech.get("pdf_page"),
    }


# ---------------------------------------------------------------------------
# BundestagSpeechesConnector
# ---------------------------------------------------------------------------


class BundestagSpeechesConnector(BaseConnector):
    """Connector for Bundestag plenary speeches → parliamentary_speech ChunkRecords.

    Live incremental connector:
        discover(since) → fetch → normalize → [runner embeds + upserts]

    Discovery is a per-Wahlperiode SET-DIFFERENCE against the store (protocols
    in DIP minus protocols whose DIP chunks are already stored), plus a
    recent-update sweep over DIP's ``aktualisiert`` timestamp so transcript
    corrections propagate. The runner's Qdrant-derived cursor is accepted (ABC
    contract) but ignored — a date cursor was order-dependent (another source
    or Wahlperiode advancing the shared max starved DIP backfills) and lost
    protocols that failed longer than a lookback window.

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

    # The runner still derives a cursor (ABC contract) even though discover()
    # ignores it; unscoped so the derivation stays cheap and meaningful in logs.
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
    # 1. discover — per-Wahlperiode set-difference + recent-update sweep
    # ------------------------------------------------------------------

    def _get_ingested_protocol_ids(self) -> set[str]:
        """Return protocol ids (DIP document ids) with stored DIP chunks for
        this Wahlperiode.

        Reads ``source_parent_key`` ("parliamentary_speech:dip:<protocol_id>",
        stamped by the runner) from every dip point of the configured
        Wahlperiode. Points written before parent keys existed are simply not
        counted — their protocols are re-discovered and become cheap
        content-hash present-skips.

        Returns the empty set when no store client is available (standalone use
        outside the runner): everything is then discovered, which is safe —
        the runner's already-present guard keeps re-processing cheap.
        """
        from qdrant_client import models  # noqa: PLC0415

        qdrant = (
            self._store_client
            if self._store_client is not None
            else (self._get_qdrant())
        )
        if qdrant is None:
            return set()
        collection_name = self._store_collection or self._collection_name
        ingested: set[str] = set()
        scroll_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="source_type",
                    match=models.MatchValue(value=self.source_type),
                ),
                models.FieldCondition(
                    key="source", match=models.MatchValue(value="dip")
                ),
                models.FieldCondition(
                    key="wahlperiode",
                    match=models.MatchValue(value=self._wahlperiode),
                ),
            ]
        )
        next_offset = None
        try:
            while True:
                points, next_offset = qdrant.scroll(
                    collection_name=collection_name,
                    scroll_filter=scroll_filter,
                    limit=1000,
                    offset=next_offset,
                    with_payload=["source_parent_key"],
                    with_vectors=False,
                )
                for p in points:
                    parent_key = (p.payload or {}).get("source_parent_key") or ""
                    # "parliamentary_speech:dip:<protocol_id>" → protocol_id
                    if parent_key:
                        ingested.add(str(parent_key).rsplit(":", 1)[-1])
                if next_offset is None:
                    break
        except Exception as exc:  # noqa: BLE001 — store unreachable → discover all
            logger.warning(
                "set-difference discovery: store scroll failed (%s) — "
                "treating store as empty (already-present items skip cheaply)",
                exc,
            )
            return set()
        return ingested

    def discover(self, since: Optional[int]) -> list[str]:
        """Return protocol ids to process for the configured Wahlperiode.

        SET-DIFFERENCE + UPDATE SWEEP, no date cursor:
          1. Enumerate ALL /plenarprotokoll metadata for f.wahlperiode
             (cheap catalogue pages, no XML), filtered to herausgeber "BT".
          2. Set-difference: keep protocols with no stored DIP chunks — this
             re-surfaces every transient failure forever (a max(external_id)
             watermark permanently lost anything that failed longer than a
             lookback window) and is immune to another source or Wahlperiode
             advancing a shared cursor.
          3. Update sweep: ALSO keep already-ingested protocols whose DIP
             ``aktualisiert`` timestamp is within _UPDATE_SWEEP_DAYS, so
             upstream transcript corrections are re-fetched; the runner's
             content_hash guard rewrites only real changes.

        Re-sorts ascending by (datum, id) — DIP returns DESC.
        Populates self._protocols (per-run cache).
        Loads self._mdb_lookup once per run.

        Args:
            since: Runner-derived cursor, accepted for the ABC contract but
                   IGNORED — set-difference supersedes it.

        Returns:
            List of protocol id strings sorted ascending by (datum, id).
        """
        params: dict = {"f.wahlperiode": self._wahlperiode}

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

        ingested = self._get_ingested_protocol_ids()
        sweep_floor = (
            date_type.today() - timedelta(days=_UPDATE_SWEEP_DAYS)
        ).isoformat()
        selected: list[dict] = []
        for doc in docs:
            doc_id = str(doc.get("id") or "")
            if doc_id not in ingested:
                selected.append(doc)  # new or previously failed → ingest
                continue
            # Already ingested: re-surface only when DIP marked it updated
            # recently (aktualisiert is an ISO timestamp; prefix compare on the
            # date part is safe for ISO-8601).
            aktualisiert = str(doc.get("aktualisiert") or "")
            if aktualisiert and aktualisiert[:10] >= sweep_floor:
                selected.append(doc)

        # DIP sorts DESC; BaseConnector.discover contract wants ASC.
        # Re-sort ascending by (datum, id) so run_connector processes oldest-first.
        selected.sort(key=lambda d: (d.get("datum") or "", str(d.get("id") or "")))

        # Populate per-run cache
        self._protocols = {str(d["id"]): d for d in selected}

        # Load MdB-Stammdaten once per run (cached — never load per-fetch).
        # ensure_* fetches on a cache miss and fails loud if the master data is
        # unavailable, rather than degrading every minister/president to "unbekannt".
        if self._mdb_lookup is None:
            self._mdb_lookup = ensure_mdb_lookup(_MDB_PATH)

        return [str(d["id"]) for d in selected]

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

        # The parser's pdf_page is an arithmetic estimate that ignores the PDF's
        # unnumbered front matter (title + table of contents), so its deep links
        # land short by that many pages. Resolve the protocol-wide offset from
        # the PDF itself (one download per protocol, validated against sampled
        # printed pages). Failures keep the estimates — a close-but-shifted
        # deep link beats none, and a protocol is never skipped over citation
        # polish.
        pdf_url = fundstelle.get("pdf_url") or None
        samples = _page_offset_samples(speeches)
        if pdf_url and samples:
            reader = fetch_pdf_reader(pdf_url)
            offset = resolve_page_offset(reader, samples) if reader else None
            if offset:
                for speech in speeches:
                    if isinstance(speech.get("pdf_page"), int):
                        speech["pdf_page"] += offset
            elif offset is None:
                logger.warning(
                    "protocol %s: front-matter offset undeterminable — "
                    "keeping arithmetic pdf_page estimates",
                    external_id,
                )

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
            XML <fraktion> → normalize_party → MdB-Stammdaten fallback (by
            speaker id, then by name). Non-MdB speakers (999… ids: federal /
            state ministers, state secretaries, Ministerpräsidenten,
            Bundesrat members) are KEPT — their speeches are real
            parliamentary content. Ministers who are also MdBs resolve to
            their party via the name lookup; genuinely party-less or
            unresolvable speakers quarantine as "unbekannt" (surfaced in the
            runner's chunks_unbekannt drift signal) rather than being
            silently dropped from the corpus.

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

        # Build speech rows, skipping only empty-text speeches. Non-MdB
        # speakers (999… ids) are kept — see the docstring's party-resolution
        # policy; dropping them removed entire minister/Ministerpräsident
        # speeches from the corpus.
        rows: list[dict] = []
        for speech in speeches:
            if not speech.get("text"):
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

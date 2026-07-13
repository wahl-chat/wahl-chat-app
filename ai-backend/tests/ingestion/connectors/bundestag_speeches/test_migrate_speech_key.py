# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Tests for migrate_speech_key.py — the one-off legacy DIP speech_key backfill.

Covers (dry-run / fake-Qdrant only — NEVER touches a live store or OpenAI):
  - PARITY: the migration computes the SAME speech_key the live DIP connector
    would produce for the same speech (agenda recovered by re-parsing XML).
  - NO RE-EMBED: no vectors are ever written; the fake Qdrant's upsert is never
    called; every set_payload stamps only {"speech_key", "source"}.
  - DRY-RUN default: run_migration(apply=False) mutates nothing.
  - APPLY: run_migration(apply=True) stamps source="dip" + speech_key on ALL
    chunks sharing a source_item_id.
  - IDEMPOTENCY: after --apply the (now source="dip") chunks are no longer
    selected, so a second build_plan reports 0 pending speeches.
  - GRACEFUL A6 FALLBACK: a speech whose protocol XML is unavailable gets a
    no-agenda speech_key without crashing.
"""

from __future__ import annotations

import io
from typing import Any, Optional

from src.ingestion.connectors.bundestag_speeches import migrate_speech_key as mig
from src.ingestion.connectors.bundestag_speeches.mappers import corpus as corpus_mapper
from src.ingestion.connectors.bundestag_speeches.parser import parse_speeches_from_xml
from src.ingestion.schemas import SourceType


# ---------------------------------------------------------------------------
# Fixture protocol XML — agenda-bearing (<tagesordnungspunkt top-id="20">)
# ---------------------------------------------------------------------------

_PROTOCOL_XML = """<?xml version="1.0" encoding="UTF-8"?>
<sitzungsverlauf>
  <sitzungstitel>101. Sitzung des Deutschen Bundestages</sitzungstitel>
  <tagesordnungspunkt top-id="20">
    <rede id="ID2100010">
      <p klasse="redner">
        <redner id="11004870">
          <name>
            <vorname>Olaf</vorname>
            <nachname>Scholz</nachname>
            <fraktion>SPD</fraktion>
          </name>
        </redner>Olaf Scholz (SPD):</p>
      <p klasse="J">
        Wir diskutieren heute ueber die Zukunft der Energiewende in Deutschland.
      </p>
    </rede>
  </tagesordnungspunkt>
</sitzungsverlauf>
"""

_PROTOCOL_API_ID = "proto-1"
# BL-01: real legacy chunks stored the INTERNAL numeric DIP doc id in
# meta.protocol_id (NO slash) — NOT the "wp/session" dokumentnummer. The session
# must therefore be recovered from the freshly re-fetched protocol's
# dokumentnummer, never from this stored value.
_INTERNAL_PROTOCOL_ID = "5701"  # stored legacy meta.protocol_id (no "/")
_DOKUMENTNUMMER = "20/101"  # recovered from the re-fetched protocol document
_WAHLPERIODE = 20
_SID = "sid-scholz-1"


def _fixture_speech() -> dict:
    """Parse the fixture XML the way the live connector does (for parity checks)."""
    speeches = parse_speeches_from_xml(_PROTOCOL_XML)
    assert len(speeches) == 1
    return speeches[0]


def _live_connector_speech_key() -> Optional[str]:
    """The speech_key the LIVE DIP connector would compute for the fixture speech.

    Mirrors connector._build_speech_row → corpus_mapper.compute_speech_key: the
    row carries wahlperiode, dokumentnummer protocol_id, the parsed speaker_name,
    and the agenda_top_id recovered from the enclosing <tagesordnungspunkt>.
    """
    speech = _fixture_speech()
    row = {
        "wahlperiode": _WAHLPERIODE,
        "protocol_id": _DOKUMENTNUMMER,  # live connector stores the dokumentnummer form
        "speaker_name": speech.get("speaker_name"),
        "agenda_top_id": speech.get("agenda_top_id"),
    }
    return corpus_mapper.compute_speech_key(row)


# ---------------------------------------------------------------------------
# Minimal in-memory fake Qdrant (scroll + set_payload; upsert must NEVER fire)
# ---------------------------------------------------------------------------


class _FakePoint:
    def __init__(self, point_id: str, payload: dict) -> None:
        self.id = point_id
        self.payload = payload


def _payload_is_empty(payload: dict, key: str) -> bool:
    """Mirror Qdrant IsEmptyCondition: field absent / None / empty collection."""
    if key not in payload:
        return True
    val = payload[key]
    return val is None or val == "" or val == [] or val == {}


class _FakeQdrant:
    """Faithful-enough Qdrant stand-in for the migration's scroll/set_payload path.

    Supports exactly the filter shapes the migration uses:
      - scroll: must FieldCondition(MatchValue) + IsEmptyCondition
      - set_payload: FilterSelector(must FieldCondition(source_item_id MatchValue))
    Raises if upsert is called (guards the "no re-embed / no vector write" invariant).
    """

    def __init__(self, points: list[_FakePoint]) -> None:
        self._points = points
        self.upsert_calls = 0
        self.set_payload_calls: list[dict] = []

    # --- filter matching -----------------------------------------------------

    @staticmethod
    def _match_conditions(payload: dict, flt: Any) -> bool:
        for cond in getattr(flt, "must", None) or []:
            # IsEmptyCondition
            is_empty = getattr(cond, "is_empty", None)
            if is_empty is not None:
                if not _payload_is_empty(payload, is_empty.key):
                    return False
                continue
            # FieldCondition(MatchValue)
            key = getattr(cond, "key", None)
            match = getattr(cond, "match", None)
            want = getattr(match, "value", None)
            if payload.get(key) != want:
                return False
        return True

    # --- API surface used by the migration -----------------------------------

    def scroll(
        self,
        collection_name: str,
        scroll_filter: Any = None,
        limit: int = 256,
        offset: Any = None,
        with_payload: bool = True,
        with_vectors: bool = False,
    ):
        start = offset or 0
        matched = [
            p for p in self._points if self._match_conditions(p.payload, scroll_filter)
        ]
        page = matched[start : start + limit]
        next_offset = start + limit if start + limit < len(matched) else None
        return page, next_offset

    def set_payload(
        self,
        collection_name: str,
        payload: dict,
        points: Any = None,
        wait: bool = True,
    ):
        self.set_payload_calls.append(dict(payload))
        flt = getattr(points, "filter", None)
        for p in self._points:
            if flt is not None and self._match_conditions(p.payload, flt):
                p.payload.update(payload)

    def upsert(self, *args, **kwargs):  # pragma: no cover - must never be called
        self.upsert_calls += 1
        raise AssertionError("upsert() called — migration must NOT write vectors")


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _legacy_chunk(chunk_index: int, *, xml_rede_id: str = "ID2100010") -> _FakePoint:
    """A legacy DIP chunk payload: no `source`, agenda not stored, meta populated.

    meta.protocol_id is the INTERNAL numeric DIP doc id (no "/") exactly as real
    legacy chunks stored it (BL-01) — the migration must NOT trust it for the
    session. citation_title likewise embeds the internal id (MED-03 normalises it).
    """
    speech = _fixture_speech()
    return _FakePoint(
        point_id=f"{_SID}-{chunk_index}",
        payload={
            "source_type": SourceType.PARLIAMENTARY_SPEECH.value,
            "source_item_id": _SID,
            "chunk_index": chunk_index,
            "wahlperiode": _WAHLPERIODE,
            "citation_title": f"Olaf Scholz, 2024-01-01 (Protokoll {_INTERNAL_PROTOCOL_ID})",
            # NOTE: no "source" field — this is what marks it legacy.
            "meta": {
                "protocol_id": _INTERNAL_PROTOCOL_ID,
                "protocol_api_id": _PROTOCOL_API_ID,
                "person_id": "11004870",
                "speaker_name": speech.get("speaker_name"),
                "xml_rede_id": xml_rede_id,
            },
        },
    )


def _resolver(
    mapping: dict[str, Optional[str]],
    *,
    dokumentnummer: Optional[str] = _DOKUMENTNUMMER,
) -> mig.ProtocolResolver:
    """Fake resolver: proto_api_id → ResolvedProtocol(dokumentnummer, xml_text).

    A key absent from *mapping* → total lookup failure (None). A present key with
    a None value → the protocol resolved (dokumentnummer known) but its XML is
    unavailable (A6). ``dokumentnummer=None`` simulates a protocol whose "wp/session"
    form could not be recovered at all.
    """
    def _resolve(protocol_api_id: str) -> Optional[mig.ResolvedProtocol]:
        if protocol_api_id not in mapping:
            return None
        return mig.ResolvedProtocol(
            dokumentnummer=dokumentnummer,
            xml_text=mapping[protocol_api_id],
        )

    return _resolve


# ===========================================================================
# Tests
# ===========================================================================


def test_speech_key_parity_with_live_connector():
    """Migration key == live-connector key, and the agenda component is recovered."""
    qdrant = _FakeQdrant([_legacy_chunk(0), _legacy_chunk(1)])
    resolve = _resolver({_PROTOCOL_API_ID: _PROTOCOL_XML})

    plan = mig.build_plan(qdrant, "wahlchat_chunks_dev", resolve)

    assert plan.total_speeches == 1  # two chunks collapse to one source_item_id
    entry = plan.entries[0]
    live_key = _live_connector_speech_key()
    assert entry.speech_key == live_key
    # BL-01: session recovered from the re-fetched dokumentnummer "20/101" → 101.
    assert entry.speech_key == "de-20-101-olaf-scholz-top20"
    # Agenda was recovered from <tagesordnungspunkt top-id="20"> → non-empty slug.
    assert entry.speech_key is not None and entry.speech_key.endswith("-top20")
    assert entry.no_agenda is False
    assert entry.agenda_top_id == "20"


def test_bl01_recovers_session_from_dokumentnummer_not_stored_internal_id():
    """BL-01 regression: legacy meta.protocol_id is the internal id (no slash).

    Before the fix the migration fed the stored internal id ("5701") into
    compute_speech_key, whose ``protocol_id.split("/")[1]`` returned None → EVERY
    legacy chunk got speech_key=None. This asserts the session is instead
    recovered from the freshly re-fetched dokumentnummer ("20/101" → 101).
    """
    qdrant = _FakeQdrant([_legacy_chunk(0)])
    resolve = _resolver({_PROTOCOL_API_ID: _PROTOCOL_XML})
    entry = mig.build_plan(qdrant, "wahlchat_chunks_dev", resolve).entries[0]
    assert entry.speech_key == "de-20-101-olaf-scholz-top20"
    assert entry.speech_key == _live_connector_speech_key()


def test_bl01_no_dokumentnummer_and_internal_id_yields_no_key():
    """Without a recoverable "wp/session" the migration stamps source only.

    Proves the recovery depends on the dokumentnummer: with no dokumentnummer and
    a stored internal id lacking "/", speech_key stays None (never a mismatched key).
    """
    qdrant = _FakeQdrant([_legacy_chunk(0)])
    resolve = _resolver({_PROTOCOL_API_ID: _PROTOCOL_XML}, dokumentnummer=None)
    entry = mig.build_plan(qdrant, "wahlchat_chunks_dev", resolve).entries[0]
    assert entry.speech_key is None


def test_apply_stamps_all_chunks_and_writes_no_vectors():
    """--apply stamps source+speech_key on every chunk; upsert never fires."""
    chunks = [_legacy_chunk(0), _legacy_chunk(1)]
    qdrant = _FakeQdrant(chunks)
    resolve = _resolver({_PROTOCOL_API_ID: _PROTOCOL_XML})

    mig.run_migration(
        qdrant, "wahlchat_chunks_dev", resolve, apply=True, out=io.StringIO()
    )

    # No vectors written.
    assert qdrant.upsert_calls == 0
    # Exactly one set_payload per speech. The stamp carries the two dedup fields
    # PLUS the MED-03 normalisation (meta + citation_title) — never a vector.
    assert len(qdrant.set_payload_calls) == 1
    stamped = qdrant.set_payload_calls[0]
    assert set(stamped.keys()) == {"speech_key", "source", "meta", "citation_title"}
    assert stamped["source"] == "dip"
    # BOTH chunks of the speech now carry the stamp.
    for p in chunks:
        assert p.payload["source"] == "dip"
        assert p.payload["speech_key"] == stamped["speech_key"]


def test_med03_normalizes_protocol_id_and_citation_title():
    """MED-03: apply rewrites legacy internal-id meta.protocol_id + citation_title.

    Legacy chunks stored the internal DIP doc id ("5701") in meta.protocol_id and
    "(Protokoll 5701)" in citation_title. After --apply both must carry the
    dokumentnummer "20/101" form (set_payload only, no re-embed), while the rest
    of meta (person_id, speaker_name, xml_rede_id, protocol_api_id) is preserved.
    """
    chunks = [_legacy_chunk(0), _legacy_chunk(1)]
    qdrant = _FakeQdrant(chunks)
    resolve = _resolver({_PROTOCOL_API_ID: _PROTOCOL_XML})

    mig.run_migration(
        qdrant, "wahlchat_chunks_dev", resolve, apply=True, out=io.StringIO()
    )

    for p in chunks:
        assert p.payload["meta"]["protocol_id"] == _DOKUMENTNUMMER
        # Other meta fields survive the wholesale meta replacement.
        assert p.payload["meta"]["protocol_api_id"] == _PROTOCOL_API_ID
        assert p.payload["meta"]["person_id"] == "11004870"
        assert p.payload["meta"]["xml_rede_id"] == "ID2100010"
        assert f"(Protokoll {_DOKUMENTNUMMER})" in p.payload["citation_title"]
        assert _INTERNAL_PROTOCOL_ID not in p.payload["citation_title"]


def test_med03_skips_normalization_without_dokumentnummer():
    """No dokumentnummer → no meta/citation rewrite (only source stamped)."""
    chunks = [_legacy_chunk(0)]
    qdrant = _FakeQdrant(chunks)
    resolve = _resolver({_PROTOCOL_API_ID: _PROTOCOL_XML}, dokumentnummer=None)

    mig.run_migration(
        qdrant, "wahlchat_chunks_dev", resolve, apply=True, out=io.StringIO()
    )

    stamped = qdrant.set_payload_calls[0]
    assert "meta" not in stamped and "citation_title" not in stamped
    assert chunks[0].payload["meta"]["protocol_id"] == _INTERNAL_PROTOCOL_ID


def test_dry_run_mutates_nothing():
    """Default dry-run computes the plan but issues no set_payload / no writes."""
    chunks = [_legacy_chunk(0)]
    qdrant = _FakeQdrant(chunks)
    resolve = _resolver({_PROTOCOL_API_ID: _PROTOCOL_XML})

    plan = mig.run_migration(
        qdrant, "wahlchat_chunks_dev", resolve, apply=False, out=io.StringIO()
    )

    assert plan.total_speeches == 1
    assert qdrant.set_payload_calls == []
    assert qdrant.upsert_calls == 0
    assert "source" not in chunks[0].payload  # untouched


def test_idempotent_second_run_reports_zero():
    """After --apply, stamped chunks are no longer selected → second plan is empty."""
    chunks = [_legacy_chunk(0), _legacy_chunk(1)]
    qdrant = _FakeQdrant(chunks)
    resolve = _resolver({_PROTOCOL_API_ID: _PROTOCOL_XML})

    mig.run_migration(qdrant, "wahlchat_chunks_dev", resolve, apply=True, out=io.StringIO())

    # Re-scan: every chunk now has source="dip" → IsEmpty(source) matches nothing.
    second = mig.build_plan(qdrant, "wahlchat_chunks_dev", resolve)
    assert second.total_speeches == 0


def test_missing_xml_falls_back_to_no_agenda_key():
    """A6: protocol XML unavailable → valid no-agenda key, no crash, logged."""
    qdrant = _FakeQdrant([_legacy_chunk(0)])
    resolve = _resolver({_PROTOCOL_API_ID: None})  # XML gone

    plan = mig.build_plan(qdrant, "wahlchat_chunks_dev", resolve)

    entry = plan.entries[0]
    assert entry.no_agenda is True
    assert entry.speech_key is not None  # still a valid key
    assert entry.speech_key.endswith("-")  # empty agenda component
    assert _PROTOCOL_API_ID in plan.unresolved_protocols
    assert plan.no_agenda_count == 1


def test_no_agenda_key_differs_from_agenda_key():
    """The no-agenda fallback key is a strict prefix of the agenda-bearing key."""
    with_agenda = mig.build_plan(
        _FakeQdrant([_legacy_chunk(0)]),
        "wahlchat_chunks_dev",
        _resolver({_PROTOCOL_API_ID: _PROTOCOL_XML}),
    ).entries[0]
    without_agenda = mig.build_plan(
        _FakeQdrant([_legacy_chunk(0)]),
        "wahlchat_chunks_dev",
        _resolver({_PROTOCOL_API_ID: None}),
    ).entries[0]

    assert with_agenda.speech_key == without_agenda.speech_key + "top20"


def test_no_reembed_grep_invariant():
    """The migration source contains no embedding call surface (acceptance criterion)."""
    from pathlib import Path

    src = Path(mig.__file__).read_text(encoding="utf-8")
    for needle in ("embed", "OpenAIEmbeddings", "_embed_texts"):
        assert needle not in src, f"migration must not reference {needle!r}"

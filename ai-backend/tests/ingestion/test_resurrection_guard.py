# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Resurrection-guard integration test — fake Qdrant.

The DIP connector must consult the shared indexed `speech_key` BEFORE inserting
and skip any speech already superseded by op — durable even across a full DIP
backfill / cursor reset (`since=None`). Otherwise a cursor reset would
re-insert the very duplicates op just deleted.
"""

from __future__ import annotations


class _SeededQdrant:
    """Fake Qdrant whose scroll() returns one op-owned point for speech_key X."""

    def __init__(self, superseded_key: str) -> None:
        self._key = superseded_key
        self.upserted_keys: list[str] = []

    def scroll(self, *a, **k):  # noqa: ANN002, ANN003, ANN201
        import types

        point = types.SimpleNamespace(payload={"speech_key": self._key, "source": "op"})
        return ([point], None)

    def upsert(self, *a, **k) -> None:  # noqa: ANN002, ANN003
        # Record any speech_key that reached upsert (a guard failure).
        for p in k.get("points") or (a[1] if len(a) > 1 else []):
            payload = getattr(p, "payload", {}) or {}
            if payload.get("speech_key"):
                self.upserted_keys.append(payload["speech_key"])


def test_dip_skips_op_superseded_speech_even_on_cursor_reset() -> None:
    """DIP skips inserting a speech whose speech_key is already op-owned.

    Simulate a cursor reset (`since=None`): even a full backfill must NOT
    resurrect the op-superseded speech.
    """
    from src.ingestion.connectors.bundestag_speeches.connector import (
        is_op_superseded as guard,
    )

    superseded_key = "de-20-101-mareike-lotte-wulf-top20"
    qdrant = _SeededQdrant(superseded_key)

    # The guard, given the shared key, must report the speech as op-superseded
    # (so DIP normalize/insert skips it) regardless of the incremental cursor.
    result = guard(qdrant, "wahlchat_chunks_dev", superseded_key)
    # Accept either a boolean "is superseded" or a set/list of superseded keys.
    if isinstance(result, bool):
        assert result is True, "DIP must treat the op-superseded speech as skip"
    else:
        assert superseded_key in set(result), (
            "op-superseded speech_key must appear in the guard's skip set"
        )
    assert superseded_key not in qdrant.upserted_keys, (
        "DIP must not re-insert an op-superseded speech even on cursor reset (since=None)"
    )


class _ConditionalQdrant:
    """Fake Qdrant returning an op point only for a specific superseded speech_key.

    The op point carries the op speech's TEXT so the precise (text-matching)
    resurrection guard recognises it as the SAME speech as the DIP row being
    inserted (a bare speech_key match is no longer sufficient)."""

    def __init__(self, superseded_key: str, superseded_text: str) -> None:
        self._key = superseded_key
        self._text = superseded_text

    def scroll(self, *a, **k):  # noqa: ANN002, ANN003, ANN201
        import types

        flt = k.get("scroll_filter")
        wanted = None
        for cond in getattr(flt, "must", None) or []:
            if getattr(cond, "key", None) == "speech_key":
                wanted = getattr(getattr(cond, "match", None), "value", None)
        if wanted == self._key:
            point = types.SimpleNamespace(
                payload={
                    "speech_key": self._key,
                    "source": "op",
                    "source_item_id": "op-superseded",
                    "text": self._text,
                }
            )
            return ([point], None)
        return ([], None)


def test_dip_normalize_skips_op_superseded_speech() -> None:
    """End-to-end: connector.normalize() drops the op-superseded speech, keeps others.

    Builds a connector via object.__new__ (bypassing DIP_API_KEY), injects a fake
    Qdrant that reports ONE speech_key as op-owned, and asserts normalize() emits
    chunks ONLY for the non-superseded speech — even with a full-backfill raw.
    """
    from src.ingestion.connectors.bundestag_speeches.connector import (
        BundestagSpeechesConnector,
    )
    from src.ingestion.connectors.bundestag_speeches.mappers import corpus

    superseded_key = "de-21-99-superseded-speaker-"
    keep_key = "de-21-99-fresh-speaker-"
    superseded_text = "Diese Rede wurde von op abgeloest."

    conn = object.__new__(BundestagSpeechesConnector)
    conn._mdb_lookup = {"by_id": {}, "by_name": {}}
    conn._qdrant = _ConditionalQdrant(superseded_key, superseded_text)
    conn._qdrant_lazy_enabled = False
    conn._collection_name = "wahlchat_chunks_dev"

    raw = {
        "protocol": {
            "id": "5678",
            "dokumentnummer": "21/99",
            "datum": "2026-06-01",
            "wahlperiode": 21,
            "fundstelle": {"pdf_url": None},
        },
        "speeches": [
            {
                "speaker_xml_id": "11000001",
                "speaker_name": "Superseded Speaker",
                "party": "SPD",
                "text": "Diese Rede wurde von op abgeloest.",
                "xml_rede_id": "ID99001",
            },
            {
                "speaker_xml_id": "11000002",
                "speaker_name": "Fresh Speaker",
                "party": "SPD",
                "text": "Diese Rede ist nur bei DIP vorhanden.",
                "xml_rede_id": "ID99002",
            },
        ],
        "mdb_lookup": {"by_id": {}, "by_name": {}},
    }

    # Sanity: the two speeches produce the expected shared keys.
    assert (
        corpus.compute_speech_key(
            {
                "wahlperiode": 21,
                "protocol_id": "21/99",
                "speaker_name": "Superseded Speaker",
                "agenda_top_id": None,
            }
        )
        == superseded_key
    )
    assert (
        corpus.compute_speech_key(
            {
                "wahlperiode": 21,
                "protocol_id": "21/99",
                "speaker_name": "Fresh Speaker",
                "agenda_top_id": None,
            }
        )
        == keep_key
    )

    records = conn.normalize(raw)
    keys = {r.speech_key for r in records}
    assert superseded_key not in keys, (
        "op-superseded speech must be skipped by normalize()"
    )
    assert keep_key in keys, "non-superseded DIP speech must still be inserted"
    assert all(r.source == "dip" for r in records)


class _MultiChunkQdrant:
    """Fake Qdrant serving one op speech as TWO chunks, deliberately out of order."""

    def __init__(self, key: str, parts: list[tuple[int, str]]) -> None:
        self._key = key
        self._parts = parts
        self._served = False

    def scroll(self, *a, **k):  # noqa: ANN002, ANN003, ANN201
        import types

        if self._served:
            return ([], None)
        self._served = True
        points = [
            types.SimpleNamespace(
                payload={
                    "speech_key": self._key,
                    "source": "op",
                    "source_item_id": "op-multichunk",
                    "text": text,
                    "chunk_index": idx,
                }
            )
            for idx, text in self._parts
        ]
        return (points, None)


def test_is_op_superseded_joins_multichunk_op_speech_in_chunk_order() -> None:
    """Regression: a 2-chunk op speech scrolled in REVERSE chunk order must
    still match the DIP twin's full text — joined by chunk_index, never scroll
    order ("B+A" vs "A+B" scores ≈0.5 < 0.85 → silent resurrection)."""
    from src.ingestion.connectors.bundestag_speeches.connector import is_op_superseded

    key = "de-20-101-mareike-lotte-wulf-top20"
    part_a = "Sehr geehrte Frau Praesidentin! Liebe Kolleginnen und Kollegen im Saal!"
    part_b = "Wir staerken die Aus- und Weiterbildungsfoerderung in diesem ganzen Land."
    # Scroll serves chunk_index=1 FIRST.
    qdrant = _MultiChunkQdrant(key, [(1, part_b), (0, part_a)])

    assert (
        is_op_superseded(
            qdrant, "wahlchat_chunks_dev", key, dip_text=f"{part_a} {part_b}"
        )
        is True
    ), "in-order join must recognise the same speech despite scroll order"


def test_is_op_superseded_empty_folded_dip_text_inserts_fail_safe() -> None:
    """A dip_text that folds to EMPTY after normalization is unverifiable —
    the guard must return False (insert; fail-safe), consistent with its posture
    everywhere else. Bare key existence is NOT proof of the same speech."""
    from src.ingestion.connectors.bundestag_speeches.connector import is_op_superseded

    key = "de-20-101-mareike-lotte-wulf-top20"
    qdrant = _ConditionalQdrant(key, "Eine ganz normale Rede mit Text.")

    # "!!! ---" folds to "" → unverifiable → insert.
    assert (
        is_op_superseded(qdrant, "wahlchat_chunks_dev", key, dip_text="!!! ---")
        is False
    )


def test_normalize_returns_empty_when_all_speeches_op_superseded() -> None:
    """A protocol whose EVERY usable speech is op-superseded is a clean
    no-op — normalize() returns [] (and reports the skipped siids) instead of
    raising 'zero usable speeches' into failed_ids on every run for 60 days."""
    from src.ingestion.connectors.bundestag_speeches.connector import (
        BundestagSpeechesConnector,
    )

    class _AllSupersededQdrant:
        """Fake Qdrant reporting EVERY speech_key as op-owned with matching text."""

        def __init__(self, text_by_any: str) -> None:
            self._text = text_by_any

        def scroll(self, *a, **k):  # noqa: ANN002, ANN003, ANN201
            import types

            point = types.SimpleNamespace(
                payload={
                    "source": "op",
                    "source_item_id": "op-x",
                    "text": self._text,
                    "chunk_index": 0,
                }
            )
            return ([point], None)

    speech_text = "Diese Rede wurde vollstaendig von op abgedeckt."
    conn = object.__new__(BundestagSpeechesConnector)
    conn._mdb_lookup = {"by_id": {}, "by_name": {}}
    conn._qdrant = _AllSupersededQdrant(speech_text)
    conn._qdrant_lazy_enabled = False
    conn._collection_name = "wahlchat_chunks_dev"

    raw = {
        "protocol": {
            "id": "4242",
            "dokumentnummer": "21/42",
            "datum": "2026-06-01",
            "wahlperiode": 21,
            "fundstelle": {"pdf_url": None},
        },
        "speeches": [
            {
                "speaker_xml_id": "11000001",
                "speaker_name": "Voll Abgedeckt",
                "party": "SPD",
                "text": speech_text,
                "xml_rede_id": "ID42001",
            }
        ],
        "mdb_lookup": {"by_id": {}, "by_name": {}},
    }

    records = conn.normalize(raw)

    assert records == [], (
        "fully-op-covered protocol must be a clean no-op, not an error"
    )
    assert len(conn.last_superseded_siids) == 1, (
        "the skipped siid must be reported for the stranded-twin cleanup"
    )


def test_is_op_superseded_precise_rejects_distinct_same_key_speech() -> None:
    """An op point under the key whose TEXT differs (a distinct speech a
    speaker gave under the same agenda item) must NOT mark this DIP speech as
    superseded — otherwise the DIP text of a speech op never aligned is lost."""
    from src.ingestion.connectors.bundestag_speeches.connector import is_op_superseded

    key = "de-20-101-mareike-lotte-wulf-top20"
    # op holds a DIFFERENT speech under the same (non-unique) key.
    qdrant = _ConditionalQdrant(
        key, "Ein voellig anderer Redebeitrag zum Thema Verkehr."
    )

    # The DIP speech we're about to insert has different text → not superseded.
    assert (
        is_op_superseded(
            qdrant,
            "wahlchat_chunks_dev",
            key,
            dip_text="Zur Kinderarmut in Deutschland.",
        )
        is False
    )
    # The same speech (matching text) IS superseded.
    assert (
        is_op_superseded(
            qdrant,
            "wahlchat_chunks_dev",
            key,
            dip_text="Ein voellig anderer Redebeitrag zum Thema Verkehr.",
        )
        is True
    )

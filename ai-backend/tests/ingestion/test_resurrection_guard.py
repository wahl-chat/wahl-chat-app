# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Resurrection-guard integration test (D-05) — fake Qdrant.

The DIP connector must consult the shared indexed `speech_key` BEFORE inserting
and skip any speech already superseded by op — durable even across a full DIP
backfill / cursor reset (`since=None`). Otherwise a cursor reset would
re-insert the very duplicates op just deleted.

Wave-0 SCAFFOLD: the guard does not exist yet. This file collects cleanly and
CAPABILITY-SKIPS until the guard lands (Wave 11-04/11-05), then runs the real
assertion against a fake Qdrant seeded with an op-superseded speech.
"""

from __future__ import annotations

import pytest


class _SeededQdrant:
    """Fake Qdrant whose scroll() returns one op-owned point for speech_key X."""

    def __init__(self, superseded_key: str) -> None:
        self._key = superseded_key
        self.upserted_keys: list[str] = []

    def scroll(self, *a, **k):  # noqa: ANN002, ANN003, ANN201
        import types

        point = types.SimpleNamespace(
            payload={"speech_key": self._key, "source": "op"}
        )
        return ([point], None)

    def upsert(self, *a, **k) -> None:  # noqa: ANN002, ANN003
        # Record any speech_key that reached upsert (a guard failure).
        for p in (k.get("points") or (a[1] if len(a) > 1 else [])):
            payload = getattr(p, "payload", {}) or {}
            if payload.get("speech_key"):
                self.upserted_keys.append(payload["speech_key"])


def _guard_capability():
    """Return the resurrection-guard callable once it exists, else None."""
    try:
        from src.ingestion.connectors.bundestag_speeches import connector as dip
    except ImportError:
        return None
    for name in ("is_op_superseded", "skip_if_op_superseded", "op_superseded_keys"):
        fn = getattr(dip, name, None)
        if fn is not None:
            return fn
    return None


def test_dip_skips_op_superseded_speech_even_on_cursor_reset() -> None:
    """D-05: DIP skips inserting a speech whose speech_key is already op-owned.

    Simulate a cursor reset (`since=None`): even a full backfill must NOT
    resurrect the op-superseded speech.
    """
    guard = _guard_capability()
    if guard is None:
        pytest.skip("DIP resurrection guard not yet implemented (11-04/05) — Wave-0 scaffold")

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
    inserted (a bare speech_key match is no longer sufficient — HIGH-1)."""

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
    assert corpus.compute_speech_key(
        {"wahlperiode": 21, "protocol_id": "21/99", "speaker_name": "Superseded Speaker", "agenda_top_id": None}
    ) == superseded_key
    assert corpus.compute_speech_key(
        {"wahlperiode": 21, "protocol_id": "21/99", "speaker_name": "Fresh Speaker", "agenda_top_id": None}
    ) == keep_key

    records = conn.normalize(raw)
    keys = {r.speech_key for r in records}
    assert superseded_key not in keys, "op-superseded speech must be skipped by normalize()"
    assert keep_key in keys, "non-superseded DIP speech must still be inserted"
    assert all(r.source == "dip" for r in records)


def test_is_op_superseded_precise_rejects_distinct_same_key_speech() -> None:
    """HIGH-1: an op point under the key whose TEXT differs (a distinct speech a
    speaker gave under the same agenda item) must NOT mark this DIP speech as
    superseded — otherwise the DIP text of a speech op never aligned is lost."""
    from src.ingestion.connectors.bundestag_speeches.connector import is_op_superseded

    key = "de-20-101-mareike-lotte-wulf-top20"
    # op holds a DIFFERENT speech under the same (non-unique) key.
    qdrant = _ConditionalQdrant(key, "Ein voellig anderer Redebeitrag zum Thema Verkehr.")

    # The DIP speech we're about to insert has different text → not superseded.
    assert (
        is_op_superseded(qdrant, "wahlchat_chunks_dev", key, dip_text="Zur Kinderarmut in Deutschland.")
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

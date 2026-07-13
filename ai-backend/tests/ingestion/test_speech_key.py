# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Golden op/DIP parity test for the shared speech_key helper (D-06/D-07/Q5).

Wave-0 SCAFFOLD: the shared module does not exist yet. The top-level
`pytest.importorskip(...)` makes this whole file SKIP cleanly until
`src.ingestion.speech_key` lands (Wave 11-02+), at which point the real
assertions run.

Covers:
  - test_op_dip_parity: the SAME real speaker fed two ways — op's discrete
    firstname+lastname vs DIP's merged `speaker_name` carrying an academic
    title — must produce BYTE-IDENTICAL keys of shape
    `de-20-101-<slug>-top20`.
"""

from __future__ import annotations

import pytest

# Wave-0 guard: SKIP until the shared speech_key helper exists.
speech_key = pytest.importorskip(
    "src.ingestion.speech_key",
    reason="shared speech_key helper not yet implemented (11-02+) — Wave-0 scaffold",
)


def _make_key(**kwargs) -> str:
    """Call make_speech_key tolerant of the exact keyword surface."""
    fn = getattr(speech_key, "make_speech_key")
    return fn(**kwargs)


def test_op_dip_parity() -> None:
    """D-06: identical speech_key from op (discrete names) and DIP (merged name+title).

    Same real speaker (Mareike Lotte Wulf, CDU/CSU), same session 101 / EP 20,
    same agenda "Tagesordnungspunkt 20" → both sources must derive the identical
    key `de-20-101-mareike-lotte-wulf-top20`.
    """
    op_key = _make_key(
        ep=20,
        session=101,
        firstname="Mareike Lotte",
        lastname="Wulf",
        agenda="Tagesordnungspunkt 20",
    )
    dip_key = _make_key(
        ep=20,
        session=101,
        speaker_name="Dr. Mareike Lotte Wulf",  # DIP merged string w/ academic title
        agenda="Tagesordnungspunkt 20",
    )

    assert op_key == dip_key, (
        f"op and DIP must derive byte-identical speech_key; got op={op_key!r} dip={dip_key!r}"
    )
    assert op_key == "de-20-101-mareike-lotte-wulf-top20", (
        f"unexpected speech_key shape: {op_key!r}"
    )


# ---------------------------------------------------------------------------
# HIGH-01: agenda-slug op/DIP parity + Zusatzpunkt/Tagesordnungspunkt distinction
# ---------------------------------------------------------------------------

_agenda_from_official = getattr(speech_key, "agenda_slug_from_official")
_agenda_from_top_id = getattr(speech_key, "agenda_slug_from_top_id")


def test_agenda_slug_zusatzpunkt_parity() -> None:
    """HIGH-01: ``Zusatzpunkt 5`` (op) and ``ZP5`` (DIP top-id) both → ``zp5``."""
    assert _agenda_from_official("Zusatzpunkt 5") == "zp5"
    assert _agenda_from_top_id("ZP5") == "zp5"
    assert _agenda_from_top_id("Z5") == "zp5"
    # And the full key agrees on both sides for the same Zusatzpunkt speech.
    op_key = _make_key(ep=20, session=101, firstname="A", lastname="B",
                       agenda="Zusatzpunkt 5")
    dip_key = _make_key(ep=20, session=101, speaker_name="A B", top_id="ZP5")
    assert op_key == dip_key == "de-20-101-a-b-zp5"


def test_agenda_slug_tagesordnungspunkt_parity() -> None:
    """HIGH-01: ``Tagesordnungspunkt 5`` (op) and ``5`` (DIP top-id) both → ``top5``."""
    assert _agenda_from_official("Tagesordnungspunkt 5") == "top5"
    assert _agenda_from_top_id("5") == "top5"
    op_key = _make_key(ep=20, session=101, firstname="A", lastname="B",
                       agenda="Tagesordnungspunkt 5")
    dip_key = _make_key(ep=20, session=101, speaker_name="A B", top_id="5")
    assert op_key == dip_key == "de-20-101-a-b-top5"


def test_agenda_slug_letter_suffix_parity() -> None:
    """HIGH-01: letter-suffixed / combined item matches on both sides (first integer).

    op ``"Tagesordnungspunkt 20 a"`` and DIP top-id ``"20a"`` must both → ``top20``
    (previously op used the TRAILING integer and produced an empty agenda → a
    missed dedup, the exact failure this phase exists to prevent).
    """
    assert _agenda_from_official("Tagesordnungspunkt 20 a") == "top20"
    assert _agenda_from_top_id("20a") == "top20"
    op_key = _make_key(ep=20, session=101, firstname="A", lastname="B",
                       agenda="Tagesordnungspunkt 20 a")
    dip_key = _make_key(ep=20, session=101, speaker_name="A B", top_id="20a")
    assert op_key == dip_key == "de-20-101-a-b-top20"


def test_zusatzpunkt_and_tagesordnungspunkt_do_not_collide() -> None:
    """HIGH-01: ZP5 and TOP5 must produce DIFFERENT keys.

    Guards against the destructive supersede-delete: if a speaker speaks under
    both ZP5 and TOP5 in one session, the two distinct speeches must NOT share a
    speech_key (else superseding the op TOP5 copy would delete the ZP5 DIP chunk).
    """
    assert _agenda_from_top_id("ZP5") != _agenda_from_top_id("5")
    assert _agenda_from_official("Zusatzpunkt 5") != _agenda_from_official(
        "Tagesordnungspunkt 5"
    )
    zp_key = _make_key(ep=20, session=101, speaker_name="A B", top_id="ZP5")
    top_key = _make_key(ep=20, session=101, speaker_name="A B", top_id="5")
    assert zp_key != top_key

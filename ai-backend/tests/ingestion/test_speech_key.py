# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Golden op/DIP parity test for the shared speech_key helper.

The shared module does not exist yet. The top-level
`pytest.importorskip(...)` makes this whole file SKIP cleanly until
`src.ingestion.speech_key` lands, at which point the real
assertions run.

Covers:
  - test_op_dip_parity: the SAME real speaker fed two ways — op's discrete
    firstname+lastname vs DIP's merged `speaker_name` carrying an academic
    title — must produce BYTE-IDENTICAL keys of shape
    `de-20-101-<slug>-top20`.
"""

from __future__ import annotations

import pytest

# SKIP until the shared speech_key helper exists.
speech_key = pytest.importorskip(
    "src.ingestion.speech_key",
    reason="shared speech_key helper not yet implemented",
)


def _make_key(**kwargs) -> str:
    """Call make_speech_key tolerant of the exact keyword surface."""
    fn = getattr(speech_key, "make_speech_key")
    return fn(**kwargs)


def test_op_dip_parity() -> None:
    """Identical speech_key from op (discrete names) and DIP (merged name+title).

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
# NFC pre-normalization — NFD input must not bypass the umlaut expansion
# ---------------------------------------------------------------------------


def test_nfd_and_nfc_names_produce_identical_slug() -> None:
    """'Körig' as NFD (o + combining diaeresis) must slugify identically to
    NFC 'Körig' — both expand ö→oe → 'koerig' (previously NFD folded to 'korig',
    a silent cross-source dedup miss)."""
    import unicodedata

    slugify = getattr(speech_key, "slugify_speaker")
    nfc_name = unicodedata.normalize("NFC", "Körig")
    nfd_name = unicodedata.normalize("NFD", "Körig")
    assert nfc_name != nfd_name, (
        "sanity: the two normal forms must differ codepoint-wise"
    )
    assert slugify(full_name=nfd_name) == slugify(full_name=nfc_name) == "koerig"


# ---------------------------------------------------------------------------
# Compound academic titles — DIP merged name vs op discrete names parity
# ---------------------------------------------------------------------------


def test_compound_title_dr_h_c_parity() -> None:
    """DIP 'Dr. h. c. Thomas Sattelberger' == op discrete names — the h/c
    fragments of the compound title must be dropped."""
    dip_key = _make_key(
        ep=20,
        session=101,
        speaker_name="Dr. h. c. Thomas Sattelberger",
        agenda="Tagesordnungspunkt 20",
    )
    op_key = _make_key(
        ep=20,
        session=101,
        firstname="Thomas",
        lastname="Sattelberger",
        agenda="Tagesordnungspunkt 20",
    )
    assert dip_key == op_key == "de-20-101-thomas-sattelberger-top20"


def test_compound_title_dr_ing_parity() -> None:
    """DIP 'Dr.-Ing. Klara Beispiel' == op discrete names ('ing' dropped)."""
    dip_key = _make_key(
        ep=21,
        session=5,
        speaker_name="Dr.-Ing. Klara Beispiel",
        agenda="Tagesordnungspunkt 3",
    )
    op_key = _make_key(
        ep=21,
        session=5,
        firstname="Klara",
        lastname="Beispiel",
        agenda="Tagesordnungspunkt 3",
    )
    assert dip_key == op_key == "de-21-5-klara-beispiel-top3"


# ---------------------------------------------------------------------------
# Name particles — DIP (namenszusatz unparsed) vs op (particle in lastname)
# ---------------------------------------------------------------------------


def test_name_particle_von_parity() -> None:
    """DIP merged 'Beatrix Storch' (parser never reads <namenszusatz>) and op
    firstname='Beatrix' lastname='von Storch' must derive one identical key —
    the particle is dropped source-independently."""
    dip_key = _make_key(
        ep=20,
        session=101,
        speaker_name="Beatrix Storch",
        agenda="Tagesordnungspunkt 20",
    )
    op_key = _make_key(
        ep=20,
        session=101,
        firstname="Beatrix",
        lastname="von Storch",
        agenda="Tagesordnungspunkt 20",
    )
    assert dip_key == op_key == "de-20-101-beatrix-storch-top20"


# ---------------------------------------------------------------------------
# Umlaut/ß + title/particle parity via BOTH make_speech_key call surfaces
# (raw names vs pre-slugified speaker_slug/agenda_slug)
# ---------------------------------------------------------------------------


def test_umlaut_and_eszett_parity_via_both_call_surfaces() -> None:
    """'Jörg Groß' must derive the same key from the raw surface (firstname/
    lastname) and the pre-slugified surface (speaker_slug/agenda_slug):
    ö→oe, ß→ss are never dropped on either path."""
    slugify = getattr(speech_key, "slugify_speaker")
    assert slugify(full_name="Müller") == slugify(lastname="Müller") == "mueller"

    raw_key = _make_key(
        ep=20,
        session=9,
        firstname="Jörg",
        lastname="Groß",
        agenda="Tagesordnungspunkt 2",
    )
    pre_key = _make_key(
        ep=20,
        session=9,
        speaker_slug=slugify(full_name="Jörg Groß"),
        agenda_slug="top2",
    )
    assert raw_key == pre_key == "de-20-9-joerg-gross-top2"


def test_title_and_particle_parity_via_both_call_surfaces() -> None:
    """Compound title + name particle stripped identically on both surfaces:
    DIP merged 'Dr. h. c. Beatrix Storch' == op pre-slugified 'von Storch'."""
    slugify = getattr(speech_key, "slugify_speaker")
    dip_key = _make_key(
        ep=20,
        session=101,
        speaker_name="Dr. h. c. Beatrix Storch",
        top_id="20",
    )
    op_key = _make_key(
        ep=20,
        session=101,
        speaker_slug=slugify(firstname="Beatrix", lastname="von Storch"),
        agenda_slug="top20",
    )
    assert dip_key == op_key == "de-20-101-beatrix-storch-top20"


# ---------------------------------------------------------------------------
# Opening segments have no DIP counterpart → empty agenda slug on both sides
# ---------------------------------------------------------------------------


def test_opening_agenda_maps_to_empty_slug() -> None:
    """op agenda_type='opening' must yield '' (DIP redes outside any
    <tagesordnungspunkt> also yield ''), so opening-segment speeches dedup."""
    _agenda = getattr(speech_key, "agenda_slug_from_official")
    assert _agenda(None, "opening") == ""
    op_key = _make_key(
        ep=20,
        session=101,
        firstname="A",
        lastname="B",
        agenda=None,
        agenda_type="opening",
    )
    dip_key = _make_key(ep=20, session=101, speaker_name="A B", top_id=None)
    assert op_key == dip_key == "de-20-101-a-b-"


# ---------------------------------------------------------------------------
# Agenda-slug op/DIP parity + Zusatzpunkt/Tagesordnungspunkt distinction
# ---------------------------------------------------------------------------

_agenda_from_official = getattr(speech_key, "agenda_slug_from_official")
_agenda_from_top_id = getattr(speech_key, "agenda_slug_from_top_id")


def test_agenda_slug_zusatzpunkt_parity() -> None:
    """``Zusatzpunkt 5`` (op) and ``ZP5`` (DIP top-id) both → ``zp5``."""
    assert _agenda_from_official("Zusatzpunkt 5") == "zp5"
    assert _agenda_from_top_id("ZP5") == "zp5"
    assert _agenda_from_top_id("Z5") == "zp5"
    # And the full key agrees on both sides for the same Zusatzpunkt speech.
    op_key = _make_key(
        ep=20, session=101, firstname="A", lastname="B", agenda="Zusatzpunkt 5"
    )
    dip_key = _make_key(ep=20, session=101, speaker_name="A B", top_id="ZP5")
    assert op_key == dip_key == "de-20-101-a-b-zp5"


def test_agenda_slug_tagesordnungspunkt_parity() -> None:
    """``Tagesordnungspunkt 5`` (op) and ``5`` (DIP top-id) both → ``top5``."""
    assert _agenda_from_official("Tagesordnungspunkt 5") == "top5"
    assert _agenda_from_top_id("5") == "top5"
    op_key = _make_key(
        ep=20, session=101, firstname="A", lastname="B", agenda="Tagesordnungspunkt 5"
    )
    dip_key = _make_key(ep=20, session=101, speaker_name="A B", top_id="5")
    assert op_key == dip_key == "de-20-101-a-b-top5"


def test_agenda_slug_letter_suffix_parity() -> None:
    """Letter-suffixed / combined item matches on both sides (first integer).

    op ``"Tagesordnungspunkt 20 a"`` and DIP top-id ``"20a"`` must both → ``top20``
    (previously op used the TRAILING integer and produced an empty agenda → a
    missed dedup, the exact failure this phase exists to prevent).
    """
    assert _agenda_from_official("Tagesordnungspunkt 20 a") == "top20"
    assert _agenda_from_top_id("20a") == "top20"
    op_key = _make_key(
        ep=20,
        session=101,
        firstname="A",
        lastname="B",
        agenda="Tagesordnungspunkt 20 a",
    )
    dip_key = _make_key(ep=20, session=101, speaker_name="A B", top_id="20a")
    assert op_key == dip_key == "de-20-101-a-b-top20"


def test_zusatzpunkt_and_tagesordnungspunkt_do_not_collide() -> None:
    """ZP5 and TOP5 must produce DIFFERENT keys.

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

# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Shared deterministic speech-key helper — imported by BOTH speech connectors
(``openparliament_tv`` and ``bundestag_speeches``), NOT owned by either.

speech_key = ``de-{ep}-{session}-{speaker_slug}-{agenda_slug}``

This is the cross-source dedup identity: the supersede-delete filter, the DIP
pre-insert resurrection guard, and the migration backfill all key on it. op
derives it from discrete ``firstname``/``lastname``; DIP derives it from a
merged ``speaker_name`` string (possibly carrying an academic title). The two
MUST produce byte-identical keys for the same speech — hence ONE shared slugify
function.

Determinism doctrine (mirrors ids.py): the slug/key rules here MUST NOT change
after the first production ingest. Any change shifts every speech_key and
silently breaks dedup, the supersede filter, and the resurrection guard across
already-stamped chunks. Treat this like the WAHL_CHAT_NS namespace: frozen.

The current rules were only safe to establish because no production ingest has
happened yet — every stored dev corpus is disposable and will be re-ingested.
Any change after a production ingest requires a full re-key migration.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

# Umlaut / eszett expansions applied BEFORE any NFKD decomposition or
# non-alphanumeric stripping — so the German characters expand to their ASCII
# digraph (ae/oe/ue/ss) instead of being decomposed to a bare base letter and
# dropped. Both cases are mapped so the transform is order-independent w.r.t.
# lowercasing.
_UMLAUT_MAP = {
    "ä": "ae",
    "Ä": "Ae",
    "ö": "oe",
    "Ö": "Oe",
    "ü": "ue",
    "Ü": "Ue",
    "ß": "ss",
    "ẞ": "Ss",
}

# Academic / role title tokens dropped from the speaker slug so DIP's merged
# "Dr. Mareike Lotte Wulf" and op's discrete firstname/lastname agree.
#
# Compound German academic titles tokenize into these fragments after the
# non-alphanumeric split: "Dr. h. c." → h, c; "Dr.-Ing." → ing; "Dr. med." →
# med; "Dr. jur." → jur; "Dr. rer. nat." → rer, nat; "Dr. rer. pol." → pol;
# "Dr. habil." → habil; "Dr. E. h." → e, h. Without them a DIP merged name like
# "Dr. h. c. Thomas Sattelberger" keeps stray h/c tokens and never matches op's
# discrete firstname/lastname key — the twin is never superseded.
#
# Single letters "e"/"h"/"c" could theoretically appear as hyphenated-name
# fragments, but real MdB surnames never slugify to a bare single letter (the
# tokenizer splits on non-alphanumerics; German surname fragments like "Meyer",
# "Lühmann", "van" are all multi-letter), so dropping them is safe here.
_TITLE_TOKENS = frozenset(
    {"dr", "prof", "h", "c", "ing", "med", "jur", "rer", "nat", "pol", "habil", "e"}
)

# Name-particle (nobiliary/preposition) tokens dropped from the speaker slug —
# SOURCE-INDEPENDENT so DIP (whose parser never reads <namenszusatz>, yielding
# "Beatrix Storch") and op (whose lastname includes the particle, "von Storch")
# agree on one key: both sides drop the particle → beatrix-storch.
_PARTICLE_TOKENS = frozenset(
    {"von", "der", "van", "de", "zu", "graf", "freiherr", "freifrau", "baron", "prinz"}
)


def _expand_umlauts(text: str) -> str:
    for src, dst in _UMLAUT_MAP.items():
        text = text.replace(src, dst)
    return text


def _ascii_fold(text: str) -> str:
    """NFKD-decompose then drop any remaining combining marks / non-ASCII."""
    decomposed = unicodedata.normalize("NFKD", text)
    return decomposed.encode("ascii", "ignore").decode("ascii")


def slugify_speaker(
    *,
    firstname: Optional[str] = None,
    lastname: Optional[str] = None,
    full_name: Optional[str] = None,
) -> str:
    """Deterministic speaker slug shared by op (discrete names) and DIP (merged).

    Accepts EITHER op's discrete ``firstname``/``lastname`` OR DIP's merged
    ``full_name``. Steps (order matters for parity):
      1. NFC-normalize (a decomposed NFD ``o`` + combining diaeresis must become
         the composed ``ö`` BEFORE the umlaut expansion, else it silently folds
         to a bare ``o``);
      2. expand umlauts ``ä→ae ö→oe ü→ue ß→ss`` BEFORE folding (never dropped);
      3. NFKD-fold remaining accents to ASCII;
      4. lowercase;
      5. tokenize on non-alphanumerics and drop academic-title tokens
         (``dr``/``prof`` + compound-title fragments) and name particles
         (``von``/``der``/``van``/...);
      6. join surviving tokens with single ``-``.

    ``"Mareike Lotte Wulf"`` and op ``firstname="Mareike Lotte", lastname="Wulf"``
    both yield ``mareike-lotte-wulf``.
    """
    if full_name is not None:
        raw = full_name
    else:
        raw = " ".join(part for part in (firstname, lastname) if part)

    raw = unicodedata.normalize("NFC", raw)
    raw = _expand_umlauts(raw)
    raw = _ascii_fold(raw)
    raw = raw.lower()

    tokens = [tok for tok in re.split(r"[^a-z0-9]+", raw) if tok]
    tokens = [
        tok
        for tok in tokens
        if tok not in _TITLE_TOKENS and tok not in _PARTICLE_TOKENS
    ]
    return "-".join(tokens)


# Agenda-item kind detection. Both sides MUST agree on kind AND number so the
# op (official-title) path and the DIP (top-id) path produce byte-identical
# slugs, while a Zusatzpunkt and a Tagesordnungspunkt with the same number stay
# DISTINCT (otherwise supersede-delete could destroy an unrelated agenda item).
# Slug shape: ``{zp|top}{n}``. Number extraction is the SAME on both
# sides: the FIRST integer found (tolerant of letter suffixes / combined items
# like "20 a" or "5 und 6" — a single deterministic rule applied identically).
_ZP_OFFICIAL_RE = re.compile(r"^\s*zusatzpunkt", re.IGNORECASE)
_FIRST_INT_RE = re.compile(r"(\d+)")


def agenda_slug_from_official(
    official_title: Optional[str],
    agenda_type: Optional[str] = None,
) -> str:
    """op agenda slug: ``"Tagesordnungspunkt 20"`` → ``top20``, ``"Zusatzpunkt 5"`` → ``zp5``.

    Rules: detect the item KIND — an official title starting with
    ``Zusatzpunkt`` → ``zp{n}``, otherwise ``top{n}`` — where ``{n}`` is the
    FIRST integer in the title (identical extraction to
    ``agenda_slug_from_top_id`` for byte-parity). ``agenda_type == "opening"``
    ALWAYS yields the empty string, even when the title contains a number
    (e.g. "Eröffnung der 90. Sitzung" must not become ``top90``): opening
    segments have NO DIP counterpart slug (DIP yields ``""`` for redes outside
    any <tagesordnungspunkt>), so any op-side opening slug would break
    cross-source dedup for opening-segment speeches. Titles without an
    integer also yield ``""`` (the graceful no-agenda fallback).
    """
    if agenda_type == "opening":
        return ""
    if official_title:
        match = _FIRST_INT_RE.search(official_title)
        if match:
            prefix = "zp" if _ZP_OFFICIAL_RE.match(official_title) else "top"
            return f"{prefix}{int(match.group(1))}"
    return ""


def agenda_slug_from_top_id(top_id: Optional[str]) -> str:
    """DIP agenda slug: ``top-id="20"`` → ``top20``, ``top-id="ZP5"`` → ``zp5``.

    Detects the item KIND — a top-id whose first non-space character is ``Z``
    (``"Z5"``/``"ZP5"``, Zusatzpunkt) → ``zp{n}``, otherwise ``top{n}`` — where
    ``{n}`` is the FIRST integer in the top-id (identical extraction to
    ``agenda_slug_from_official`` for byte-parity, tolerant of letter suffixes
    like ``"20a"``). Empty / unparseable → the empty string (no-agenda fallback).
    """
    if top_id is None:
        return ""
    text = str(top_id).strip()
    match = _FIRST_INT_RE.search(text)
    if match:
        prefix = "zp" if text[:1].upper() == "Z" else "top"
        return f"{prefix}{int(match.group(1))}"
    return ""


def make_speech_key(
    *,
    ep: int,
    session: int,
    speaker_slug: Optional[str] = None,
    agenda_slug: Optional[str] = None,
    firstname: Optional[str] = None,
    lastname: Optional[str] = None,
    speaker_name: Optional[str] = None,
    full_name: Optional[str] = None,
    agenda: Optional[str] = None,
    agenda_type: Optional[str] = None,
    top_id: Optional[str] = None,
) -> str:
    """Build the shared ``de-{ep}-{session}-{speaker_slug}-{agenda_slug}`` key.

    Two call surfaces, both deterministic and byte-identical for the same speech:
      - pre-slugified: pass ``speaker_slug`` + ``agenda_slug`` directly;
      - raw: pass op's ``firstname``/``lastname`` (or DIP's ``speaker_name`` /
        ``full_name``) and an ``agenda`` official title / ``agenda_type`` /
        ``top_id`` — this helper slugifies them via the shared functions above.
    """
    if speaker_slug is None:
        speaker_slug = slugify_speaker(
            firstname=firstname,
            lastname=lastname,
            full_name=full_name if full_name is not None else speaker_name,
        )
    if agenda_slug is None:
        if top_id is not None:
            agenda_slug = agenda_slug_from_top_id(top_id)
        else:
            agenda_slug = agenda_slug_from_official(agenda, agenda_type)

    return f"de-{ep}-{session}-{speaker_slug}-{agenda_slug}"

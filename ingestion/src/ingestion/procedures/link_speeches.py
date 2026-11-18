# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Which procedure(s) a speech belongs to, from DIP's ``aktivitaet`` index.

DIP tags every contribution in a Plenarprotokoll (speech, question, § 31
explanation) with its Vorgang. Our chunks don't carry DIP's person ids, so a
speech is matched to its speaker's activities in the same protocol by name.
A speaker with one Vorgang that day is settled by the name alone; otherwise
the page (protocol text) or the speaking order (video) picks the activity.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Optional

from ingestion.procedures.scope import EXCLUDED_TYPES
from wahlchat_common.procedures import LinkMethod

_TITLES = re.compile(
    r"\b(dr|prof|professor|h\.?\s*c|med|rer|nat|phil|jur|pol|oec|dipl|ing|habil)\b\.?"
)
_PAGE = re.compile(r"(\d+)")
# The activities a video recording of the plenary corresponds to, one each.
_SPOKEN = frozenset(
    {
        "Rede",
        "Antwort",
        "Einleitende Ausführungen und Beantwortung",
        "Regierungserklärung",
    }
)
_FUZZY_MIN = 0.88


@dataclass(frozen=True)
class Speech:
    """One speech of the protocol as our chunks describe it."""

    key: str  # source_item_id
    source: str  # "dip" | "op"
    speaker_name: str
    page: Optional[int] = None  # dip: printed start page
    order: Optional[int] = None  # op: recording order within the protocol


@dataclass(frozen=True)
class SpeechLinkResult:
    vorgang_ids: list[str]
    method: LinkMethod


def name_key(name: str) -> str:
    """'Dr. Carl-Philipp Sassenrath, MdB, CDU/CSU' → 'carl-philipp sassenrath'."""
    plain = unicodedata.normalize("NFKD", name.split(",")[0])
    plain = plain.encode("ascii", "ignore").decode().lower()
    plain = _TITLES.sub(" ", plain)
    # Single letters are initials or leftovers of titles ('h. c.').
    words = [w for w in re.findall(r"[a-z][a-z-]*", plain) if len(w) > 1]
    if not words:
        return ""
    return f"{words[0]} {words[-1]}" if len(words) > 1 else words[0]


def _page(value: Any) -> Optional[int]:
    match = _PAGE.match(str(value or ""))
    return int(match.group(1)) if match else None


def _vorgaenge(activities: list[dict[str, Any]]) -> list[str]:
    """Their procedures; single questions (Fragestunde) are none."""
    return sorted(
        {
            str(ref["id"])
            for a in activities
            for ref in a.get("vorgangsbezug") or []
            if ref.get("vorgangstyp") not in EXCLUDED_TYPES
        }
    )


def _span(activity: dict[str, Any]) -> tuple[int, int]:
    fundstelle = activity.get("fundstelle") or {}
    start = fundstelle.get("anfangsseite") or _page(fundstelle.get("seite")) or 0
    end = fundstelle.get("endseite") or start
    return int(start), int(end)


class ProtocolIndex:
    """The protocol's tagged activities, by speaker."""

    def __init__(self, activities: list[dict[str, Any]]) -> None:
        self._by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for activity in activities:
            if activity.get("vorgangsbezug"):
                self._by_name[name_key(activity.get("titel") or "")].append(activity)
        for acts in self._by_name.values():
            acts.sort(key=lambda a: (_span(a), str(a.get("id"))))

    def lookup(self, name: str) -> tuple[list[dict[str, Any]], bool]:
        """The speaker's activities, and whether the name matched only fuzzily."""
        key = name_key(name)
        if key in self._by_name:
            return self._by_name[key], False
        if not key:
            return [], False
        last = key.split()[-1]
        same_last = [k for k in self._by_name if k.split()[-1] == last]
        if len(same_last) == 1:
            return self._by_name[same_last[0]], True
        scored = sorted(
            (
                (SequenceMatcher(None, key, k, autojunk=False).ratio(), k)
                for k in self._by_name
            ),
            reverse=True,
        )
        if (
            scored
            and scored[0][0] >= _FUZZY_MIN
            and (len(scored) == 1 or scored[1][0] < scored[0][0])
        ):
            return self._by_name[scored[0][1]], True
        return [], False


def resolve_protocol(
    speeches: list[Speech], activities: list[dict[str, Any]]
) -> dict[str, SpeechLinkResult]:
    """Link every speech of one protocol; unmatched speeches get ``none``."""
    index = ProtocolIndex(activities)
    # A speaker's video speeches in order, to pair with their spoken activities.
    op_rank: dict[str, tuple[int, int]] = {}
    by_speaker: dict[str, list[Speech]] = defaultdict(list)
    for speech in speeches:
        if speech.source == "op":
            by_speaker[name_key(speech.speaker_name)].append(speech)
    for group in by_speaker.values():
        group.sort(key=lambda s: (s.order or 0, s.key))
        for rank, speech in enumerate(group):
            op_rank[speech.key] = (rank, len(group))

    out: dict[str, SpeechLinkResult] = {}
    for speech in speeches:
        acts, fuzzy = index.lookup(speech.speaker_name)
        out[speech.key] = _resolve_one(speech, acts, fuzzy, op_rank.get(speech.key))
    return out


def _resolve_one(
    speech: Speech,
    acts: list[dict[str, Any]],
    fuzzy: bool,
    rank: Optional[tuple[int, int]],
) -> SpeechLinkResult:
    result = _match(speech, acts, fuzzy, rank)
    if acts and result.method != "none" and not result.vorgang_ids:
        return SpeechLinkResult([], "out_of_scope")
    return result


def _match(
    speech: Speech,
    acts: list[dict[str, Any]],
    fuzzy: bool,
    rank: Optional[tuple[int, int]],
) -> SpeechLinkResult:
    if not acts:
        return SpeechLinkResult([], "none")
    if len({tuple(_vorgaenge([a])) for a in acts}) == 1:
        return SpeechLinkResult(_vorgaenge(acts), "fuzzy_name" if fuzzy else "name")
    if speech.page is not None:
        on_page = [a for a in acts if _span(a)[0] <= speech.page <= _span(a)[1]]
        if not on_page:
            on_page = [a for a in acts if _span(a)[0] == speech.page]
        if on_page and len({tuple(_vorgaenge([a])) for a in on_page}) == 1:
            return SpeechLinkResult(_vorgaenge(on_page), "name_page")
    if rank is not None:
        spoken = [a for a in acts if a.get("aktivitaetsart") in _SPOKEN]
        position, count = rank
        # Only when the counts agree is the n-th video the n-th speech.
        if len(spoken) == count:
            return SpeechLinkResult(_vorgaenge([spoken[position]]), "name_order")
    return SpeechLinkResult([], "none")

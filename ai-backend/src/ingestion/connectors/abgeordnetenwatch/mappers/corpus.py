# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Pure corpus mappers for the AW connector (poll -> vote_record ChunkRecords).

All functions in this module are I/O-free (no network, no Firestore, no
wall-clock) and deterministic — suitable for unit testing without mocks.

Exports:
    chunk_poll(source_item, raw)  — produces list[ChunkRecord] per AW poll

Security notes:
    XSS-into-corpus guard: field_intro HTML is stripped via
    BeautifulSoup.get_text() before embedding into chunk text.  No raw HTML
    reaches the corpus or the LLM context.

    DoS mitigation: no regex in this module; date parsing via
    date.fromisoformat (stdlib) which accepts only strict ISO 8601 YYYY-MM-DD.

    Pydantic extra="forbid": preserved on ChunkRecord — malformed
    AW fields are rejected at validation, not silently dropped.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date as date_type
from typing import Optional, Protocol
import uuid

from bs4 import BeautifulSoup

from src.ingestion.ids import make_chunk_key
from src.ingestion.schemas import (
    AuthorityTier,
    ChunkRecord,
    SourceType,
    VoteMeta,
    VoteResult,
)
from src.ingestion.connectors.abgeordnetenwatch.mappers.stance import (
    aggregate_fraction_tallies,
    derive_stance,
)
from src.ingestion.connectors.abgeordnetenwatch.topic_taxonomy_config import (
    get_relevance_levels,
)


# ---------------------------------------------------------------------------
# SourceItemLike Protocol — the five attributes chunk_poll() reads from its
# first argument.
# ---------------------------------------------------------------------------


class SourceItemLike(Protocol):
    """Structural protocol for the source_item argument to chunk_poll().

    Any object exposing these five attributes satisfies the protocol. Members
    are declared as read-only properties so FROZEN dataclasses
    (connector._SourceItem) satisfy the protocol; chunk_poll only reads them.
    """

    @property
    def source_item_id(self) -> uuid.UUID: ...

    @property
    def region(self) -> str: ...

    @property
    def authority_tier(self) -> AuthorityTier: ...

    @property
    def source_type(self) -> SourceType: ...

    @property
    def publish_date(self) -> date_type: ...

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Party ID sentinel: a vote record belongs to no single party, so its
# top-level party_id is "_all" (the real per-party ids live in party_ids).
_PARTY_ID_SENTINEL = "_all"

# Quarantine slug for unmapped fraction names.
_PARTY_SLUG_QUARANTINE = "unbekannt"

# Canonical party slug mapping from AW fraction label fragments.
# Keys are the lowercased fraction name WITHOUT the parliament-period suffix.
# The AW votes endpoint embeds fraction objects with a "label" like
# "FDP (Bundestag 2017 - 2021)"; we strip the parenthetical before mapping.
#
# AW fraction labels use German parliamentary party names (verified from the
# AW fractions endpoint).
#
# KNOWN LIMITATION (CDU/CSU): at the Bundestag, CDU and CSU sit as one joint fraction
# "CDU/CSU", so a federal vote's Union tally is attributed to slug "cdu" only. CSU has no
# separate federal fraction, so federal Union votes are addressable under "cdu" and NOT
# under "csu" — a "csu" query returns no federal vote records. Standalone-CSU labels (rare)
# still map to "csu". This is an intentional modeling choice, not a bug.
_AW_FRACTION_SLUG_MAP: dict[str, str] = {
    "spd": "spd",
    "cdu/csu": "cdu",
    "cdu": "cdu",
    "csu": "csu",
    "bündnis 90/die grünen": "gruene",
    "bündnis 90/die grüne": "gruene",
    "die grünen": "gruene",
    "grüne": "gruene",
    "fdp": "fdp",
    "afd": "afd",
    "die linke": "linke",
    "die linke.": "linke",
    "linke": "linke",
    "bsw": "bsw",
    "bsw (gruppe)": "bsw",
    "die linke. (gruppe)": "linke",
    "fraktionslos": "fraktionslos",
    # State-level parties (parenthetical suffix stripped before lookup).
    # AW fraction labels include the parliament-period: "Freie Wähler (Bayern 2023 - 2028)".
    # After _PARENS_SUFFIX_RE strips the parenthetical, the base name is looked up here.
    # Slugs kept identical to manifestos/mappers/corpus.py so cross-source retrieval
    # returns both vote_record and party_manifesto chunks for the same party.
    "freie wähler": "fw",           # Bayern, Sachsen-Anhalt, multiple states
    "ssw": "ssw",                   # Südschleswigscher Wählerverband (SH only)
    "bvb/freie wähler": "bvb-fw",  # BVB / Freie Wähler Sachsen (Brandenburg)
    "volt": "volt",                 # Volt Deutschland (multiple states)
    "piraten": "piraten",           # Piratenpartei
    "ödp": "oedp",                  # Ökologisch-Demokratische Partei
    "die basis": "basis",           # dieBasis
    "diebasis": "basis",            # dieBasis alternate label
    "bürger in wut": "biw",        # Bürger in Wut (Bremen)
    # Add further state-party labels after verifying live AW /fractions responses
    # per Landtag. The "unbekannt" quarantine safely absorbs
    # any unlisted fraction labels discovered at runtime.
}

# Regex to strip the parliament-period parenthetical from a fraction label.
# Example: "FDP (Bundestag 2017 - 2021)" -> "FDP"
# Only strips text inside the LAST pair of parentheses (defensive).
_PARENS_SUFFIX_RE = re.compile(r"\s*\([^)]*\)\s*$")

# Invisible / zero-width formatting characters that AW occasionally embeds in
# fraction names. The 20th/21st Bundestag Greens arrive as
# "BÜNDNIS 90/­DIE GRÜNEN" — a SOFT HYPHEN (U+00AD) sits between "90/" and
# "DIE", so a naive lowercase+strip lookup misses the map key and the whole
# Green fraction gets quarantined as "unbekannt" on every vote. Strip these
# before lookup. NFKC does NOT remove U+00AD, so it must be done explicitly.
_INVISIBLE_CHARS_RE = re.compile("[\u00ad\u200b\u200c\u200d\u2060\ufeff]")


def _normalize_fraction_label(label: str) -> str:
    """Normalise a fraction label for slug lookup.

    Removes invisible/zero-width formatting characters (notably the U+00AD soft
    hyphen AW puts in "BÜNDNIS 90/­DIE GRÜNEN"), then collapses internal
    whitespace runs to single spaces, strips, and lowercases.
    """
    clean = _INVISIBLE_CHARS_RE.sub("", label)
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip().lower()


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _canonical_party_slug(fraction_label: str) -> str:
    """Map an AW fraction label to a canonical party slug.

    The ``fraction.label`` in the votes endpoint response contains a
    parliament-period suffix: "FDP (Bundestag 2017 - 2021)".  We strip that
    suffix before looking up in ``_AW_FRACTION_SLUG_MAP``.

    Unknown fraction labels (including after stripping) return the quarantine
    slug ``"unbekannt"`` rather than crashing or producing an ad-hoc slug.

    Args:
        fraction_label: The ``label`` field from an AW ``fraction`` dict in
                        a votes response, e.g. ``"FDP (Bundestag 2017 - 2021)"``.

    Returns:
        Canonical party slug string, e.g. ``"fdp"``, or ``"unbekannt"``.
    """
    # Strip parenthetical parliament-period suffix, then normalise away invisible
    # formatting characters (U+00AD soft hyphen in the Greens' fraction name).
    clean = _normalize_fraction_label(_PARENS_SUFFIX_RE.sub("", fraction_label))
    return _AW_FRACTION_SLUG_MAP.get(clean, _PARTY_SLUG_QUARANTINE)


def _strip_html(html: Optional[str]) -> str:
    """Strip HTML tags from a field_intro string (XSS guard).

    Args:
        html: Raw HTML string from ``field_intro``, or ``None``.

    Returns:
        Plain text with inline whitespace collapsed, or empty string if None.
    """
    if not html:
        return ""
    return BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_topic_labels(poll: dict) -> list[str]:
    """Extract the field_topics label strings from an AW poll dict.

    Used for both the embed text and the relevance_levels taxonomy lookup
    inside :func:`chunk_poll`.

    isinstance check + str() cast before use (untrusted AW payload).
    """
    return [
        str(t["label"])
        for t in (poll.get("field_topics") or [])
        if isinstance(t, dict) and t.get("label")
    ]


def _motion_outcome(poll: dict) -> Optional[str]:
    """Derive the overall motion result from the poll's ``field_accepted`` flag.

    Best-effort: AW exposes an explicit boolean ``field_accepted`` on the poll
    node.  We do NOT infer pass/fail by summing fraction tallies — absent
    parties and quorum rules make that unreliable.

    Returns ``"angenommen"`` / ``"abgelehnt"`` / ``None`` (unknown).
    """
    accepted = poll.get("field_accepted")
    if accepted is True:
        return "angenommen"
    if accepted is False:
        return "abgelehnt"
    return None


def chunk_poll(
    source_item: SourceItemLike,
    raw: dict,
    *,
    wahlperiode: Optional[int] = None,
    legislature_period_id: Optional[int] = None,
) -> list[ChunkRecord]:
    """Produce ONE deterministic, FULLY-STAMPED ChunkRecord per AW poll.

    Design (vote-record array model + envelope/meta split):
      - The embedded ``text`` is the *subject* of the motion only — poll label,
        topic labels, and the HTML-stripped intro.  The tally is deliberately
        NOT embedded (it would pollute the vector and cluster all votes together);
        it lives in ``meta`` (a VoteMeta dict) instead.
      - ``party_ids`` is the sorted list of every participating party's slug —
        filterable via a non-tenant keyword array index; stays top-level (INDEXED).
      - ``meta`` carries a VoteMeta dict with ``vote_results`` (one VoteResult per
        fraction, sorted ascending by fraction_id for determinism) and
        ``motion_outcome``; neither is in the envelope top-level.
      - ``party_id`` is the ``_all`` sentinel: a vote belongs to no single party,
        so it opts out of per-party tenant co-location and is filtered via
        ``party_ids`` instead.

    This function owns the WHOLE record build: topic extraction
    (:func:`extract_topic_labels`), relevance_levels derivation
    (``get_relevance_levels``; the no-topics WARNING is suppressed for
    non-federal regions), and the envelope stamping (external_id, wahlperiode,
    legislature_period_id, relevance_levels).

    content_hash covers the correctness-bearing content AND the stamped
    envelope fields (region, publish_date, relevance_levels, wahlperiode,
    legislature_period_id) — so an AW_REFRESH reconcile run propagates envelope
    corrections (e.g. a re-classified topic or a fixed region), not just
    text/tally changes.

    source_item is typed as the structural SourceItemLike Protocol — the frozen
    stub built in connector.normalize() satisfies it.

    Party slugs are resolved from the ``fraction.label`` inside each vote dict via
    ``_canonical_party_slug()`` — no connector-level fraction_map needed.

    Degenerate-input guard: votes where ``fraction`` is not a
    dict are skipped by ``aggregate_fraction_tallies``.  A poll with zero usable
    tallies yields an empty list here; connector.normalize() turns that into the
    zero-tally ValueError.

    Args:
        source_item: Any SourceItemLike object with source_item_id, region,
                     authority_tier, source_type, publish_date attributes.
        raw:         Raw payload: ``{"poll": <poll dict>, "votes": <votes list>}``.
        wahlperiode: German Wahlperiode number (Bundestag only; None for
                     Landtage — state Wahlperiode ints collide across states).
        legislature_period_id: AW parliament_period ID (globally unique period key).

    Returns:
        A list with a single fully-stamped ``ChunkRecord`` (or empty when no
        usable tallies).
    """
    poll: dict = raw["poll"]
    votes: list[dict] = raw["votes"]

    poll_label: str = poll.get("label") or ""
    field_intro: Optional[str] = poll.get("field_intro")
    intro_text: str = _strip_html(field_intro)
    topic_labels: list[str] = extract_topic_labels(poll)

    # Aggregate per-fraction tallies (skips degenerate fraction=[] entries)
    tallies = aggregate_fraction_tallies(votes)
    if not tallies:
        # Zero usable tallies — let connector.normalize() raise.
        return []

    # Merge tallies by canonical party slug. Distinct fraction_ids can map to the same
    # slug (e.g. a transition-period Gruppe alongside the main fraction); summing prevents
    # one tally being silently dropped when a later lookup finds only the first by party_id.
    # Iterate fraction_ids in order so the merge itself is deterministic.
    by_slug: dict[str, dict[str, int]] = {}
    for _fraction_id, tally in sorted(tallies.items()):
        party_slug = _canonical_party_slug(tally["fraction"].get("label") or "")
        acc = by_slug.setdefault(
            party_slug, {"yes": 0, "no": 0, "abstain": 0, "no_show": 0}
        )
        acc["yes"] += tally["yes"]
        acc["no"] += tally["no"]
        acc["abstain"] += tally["abstain"]
        acc["no_show"] += tally["no_show"]

    # One VoteResult per party, ascending by slug for determinism.
    vote_results: list[VoteResult] = [
        VoteResult(
            party_id=slug,
            stance=derive_stance(t["yes"], t["no"], t["abstain"], t["no_show"]),
            yes=t["yes"],
            no=t["no"],
            abstain=t["abstain"],
            no_show=t["no_show"],
        )
        for slug, t in sorted(by_slug.items())
    ]
    party_slugs: set[str] = set(by_slug.keys())

    # Subject-only embed text — topic and tally split: tally is payload, not vector.
    text = poll_label
    if topic_labels:
        text = f"{text}\n\nThemen: {', '.join(topic_labels)}"
    if intro_text:
        text = f"{text}\n\nKontext: {intro_text}"

    chunk_key: str = make_chunk_key(source_item.source_item_id, 0)

    meta = VoteMeta(
        vote_results=vote_results,
        motion_outcome=_motion_outcome(poll),
    ).model_dump(mode="json", exclude_none=True)

    # Relevance levels from the topic taxonomy. Landtag polls routinely carry no
    # field_topics — suppress the per-poll no-topics WARNING for non-federal
    # regions (unknown-label warnings stay loud everywhere).
    relevance_levels = get_relevance_levels(
        topic_labels, warn_on_missing_topics=(source_item.region == "DE")
    )

    # Stable hash of the correctness-bearing content (embed text + tallies/outcome
    # + participating parties) PLUS the stamped envelope fields (region,
    # publish_date, relevance_levels, wahlperiode, legislature_period_id) — so an
    # AW_REFRESH reconcile run re-writes chunks whose envelope changed (e.g. a
    # re-classified topic), not only text/tally corrections.
    content_hash = hashlib.sha256(
        json.dumps(
            {
                "text": text,
                "meta": meta,
                "party_ids": sorted(party_slugs),
                "region": source_item.region,
                "publish_date": source_item.publish_date.isoformat(),
                "relevance_levels": relevance_levels,
                "wahlperiode": wahlperiode,
                "legislature_period_id": legislature_period_id,
            },
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()

    return [
        ChunkRecord(
            chunk_key=chunk_key,
            source_item_id=source_item.source_item_id,
            chunk_index=0,
            text=text,
            party_id=_PARTY_ID_SENTINEL,
            region=source_item.region,
            authority_tier=source_item.authority_tier,
            source_type=source_item.source_type,
            publish_date=source_item.publish_date,
            citation_url=poll.get("abgeordnetenwatch_url"),
            citation_title=poll_label,
            party_ids=sorted(party_slugs),
            external_id=poll["id"],
            wahlperiode=wahlperiode,
            legislature_period_id=legislature_period_id,
            relevance_levels=relevance_levels,
            content_hash=content_hash,
            meta=meta,
        )
    ]

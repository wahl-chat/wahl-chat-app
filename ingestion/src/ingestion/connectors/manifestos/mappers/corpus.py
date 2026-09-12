# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Pure transforms: AW election-program record → party_manifesto ChunkRecord list.

No I/O — every function here is deterministic and unit-testable (no network,
no OpenAI, no Qdrant, no Firestore). The connector (connector.py) and the bulk
CLI (bulk.py) both call into these helpers.

Public helpers:
  - party_to_slug         — party.label → canonical party slug
  - region_for_period     — parliament-period label → scalar region code
  - wahlperiode_for_period — Bundestag period label → Wahlperiode number
  - chunk_pages           — page-annotated text → token-bounded chunks
  - build_manifesto_records — program + chunks → list[ChunkRecord]
  - _slugify              — clean ASCII slug (umlaut transliteration)
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import date as date_type
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, ConfigDict

from ingestion.chunking import chunk_pages  # noqa: F401 (re-exported for connector)
from ingestion.party_slugs import (
    CANONICAL_PARTY_SLUGS,
    PARTY_SLUG_QUARANTINE,
    STATE_PARTY_SLUGS,
    normalize_party_label,
)
from ingestion.ids import compute_source_item_id, make_chunk_key
from ingestion.schemas import AuthorityTier, ChunkRecord, SourceType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ManifestoMeta — source-owned meta for party_manifesto chunks.
# ---------------------------------------------------------------------------


class SourceKind(StrEnum):
    """How an election-program's text was obtained (locked source rule).

    ``LINK`` — HTML page scraped via trafilatura; ``PDF`` — file downloaded and
    parsed. StrEnum so it stays a clean ``"link"``/``"pdf"`` string in logs and
    in the stored chunk ``meta``.
    """

    LINK = "link"
    PDF = "pdf"


class ManifestoMeta(BaseModel):
    """Typed builder for the manifesto chunk ``meta`` dict.

    Mirrors the schemas.py convention (VoteMeta / SpeechMeta): extra="forbid"
    rejects typo'd keys at build time; None-valued fields are dropped via
    ``model_dump(exclude_none=True)``.
    """

    model_config = ConfigDict(extra="forbid")

    aw_program_id: int
    parliament_period_id: Optional[int] = None
    parliament_period_label: Optional[str] = None
    source_kind: Optional[SourceKind] = None
    source_url: Optional[str] = None
    total_pages: Optional[int] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    # Completed-parent marker: how many chunks THIS normalize produced for the
    # whole program. Discovery compares it against the stored count so a
    # partially-committed multi-slice upsert is re-discovered and repaired
    # instead of being treated as complete forever.
    total_chunks: Optional[int] = None
    # Only stamped when the party slug quarantines to "unbekannt".
    raw_party_label: Optional[str] = None


# ---------------------------------------------------------------------------
# Party slug map — for election-program party.label
# ---------------------------------------------------------------------------

# Keys are lowercased and invisible-char-stripped (as produced by
# normalize_party_label). The major-party core and the state/regional layer are
# the shared source of truth in ingestion/src/ingestion/party_slugs.py (so a party's
# manifesto slug tenant-aligns with its vote slug); the entries below are the
# manifesto-only long-tail parties (no votes/speeches counterpart). Any label
# not here still gets a clean derived slug via _slugify — manifestos never
# quarantine an unknown party the way votes/speeches do.
_MANIFESTO_PARTY_SLUG_MAP: dict[str, str] = {
    **CANONICAL_PARTY_SLUGS,
    **STATE_PARTY_SLUGS,
    "die partei": "die-partei",
    "partei der humanisten": "pdh",
    "partei für verjüngungsforschung": "verjuengung",
    "tierschutzpartei": "tierschutzpartei",
    "bündnis c": "buendnis-c",
    "pdf": "pdf",
    "werteunion": "werteunion",
    "die gerechtigkeitspartei - team todenhöfer": "gerechtigkeit",
    "bayernpartei": "bayernpartei",
    "pdr": "pdr",
}

# ---------------------------------------------------------------------------
# German state -> ISO 3166-2 code map
# ---------------------------------------------------------------------------

_STATE_CODE_MAP: dict[str, str] = {
    "baden-württemberg": "DE-BW",
    "bayern": "DE-BY",
    "berlin": "DE-BE",
    "brandenburg": "DE-BB",
    "bremen": "DE-HB",
    "hamburg": "DE-HH",
    "hessen": "DE-HE",
    "mecklenburg-vorpommern": "DE-MV",
    "niedersachsen": "DE-NI",
    "nordrhein-westfalen": "DE-NW",
    "rheinland-pfalz": "DE-RP",
    "saarland": "DE-SL",
    "sachsen": "DE-SN",
    "sachsen-anhalt": "DE-ST",
    "schleswig-holstein": "DE-SH",
    "thüringen": "DE-TH",
}

# ---------------------------------------------------------------------------
# Bundestag election year -> Wahlperiode number
# ---------------------------------------------------------------------------

_BUNDESTAG_WAHLPERIODE: dict[str, int] = {
    "2013": 18,
    "2017": 19,
    "2021": 20,
    "2025": 21,
}


# =============================================================================
# SLUGIFY helper for directory names and derived party slugs
# =============================================================================

# Umlaut / ß transliteration table — applied before ASCII-safe slug generation.
_UMLAUT_TABLE = str.maketrans(
    {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
        "Ä": "ae",
        "Ö": "oe",
        "Ü": "ue",
    }
)


def _slugify(text: str) -> str:
    """Convert text to a clean, filesystem-safe ASCII slug.

    Steps:
      1. Transliterate German umlauts / ß to ASCII digraphs.
      2. Lowercase and strip leading/trailing whitespace.
      3. Replace every run of non-[a-z0-9] characters with a single "-".
      4. Strip leading/trailing "-".
      5. Return "unbekannt" if the result is empty.

    Examples::

        _slugify("Volt")            -> "volt"
        _slugify("Klimaliste")      -> "klimaliste"
        _slugify("Freie Sachsen")   -> "freie-sachsen"
        _slugify("Tierschutz hier!") -> "tierschutz-hier"
        _slugify("Sozialistische Gleichheitspartei") -> "sozialistische-gleichheitspartei"

    Args:
        text: Input string (party label or similar).

    Returns:
        Lowercase ASCII slug string, never empty (falls back to ``"unbekannt"``).
    """
    text = text.translate(_UMLAUT_TABLE)
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text if text else "unbekannt"


# =============================================================================
# PURE HELPERS (no I/O — unit-testable)
# =============================================================================


def party_to_slug(label: Optional[str]) -> str:
    """Map a party label from the AW election-program API to a canonical slug.

    Resolution order:
      1. Normalise the label with ``normalize_party_label`` (strips the U+00AD
         soft hyphen / zero-width chars, collapses whitespace, lowercases).
         Empty/whitespace-only -> ``"unbekannt"`` immediately.
      2. Look up in the explicit ``_MANIFESTO_PARTY_SLUG_MAP``.  Major parties
         map to their chat-context slugs (e.g. ``"gruene"``).
      3. Fall back to ``_slugify(label)`` for long-tail parties — transliterates
         umlauts and produces a clean derived slug (e.g. "Klimaliste" ->
         ``"klimaliste"``).  ``_slugify`` never returns empty (falls back to
         ``"unbekannt"``).

    Args:
        label: Raw ``party.label`` string from an AW election-program record,
               or None.

    Returns:
        Canonical party slug, e.g. ``"spd"``, ``"gruene"``, ``"klimaliste"``.
        Returns ``"unbekannt"`` only for empty/None input or an unresolvable
        label that produces no ASCII characters.
    """
    if not label:
        return PARTY_SLUG_QUARANTINE
    normalised = normalize_party_label(label)
    if not normalised:
        return PARTY_SLUG_QUARANTINE
    explicit = _MANIFESTO_PARTY_SLUG_MAP.get(normalised)
    if explicit is not None:
        return explicit
    # Derive a slug from the original label (preserves umlaut transliteration
    # that normalize_party_label strips away).
    return _slugify(label)


def region_for_period(period_label: str) -> str:
    """Derive a scalar region code from a parliament-period label.

    Mapping rules:
      - "Bundestag …"  -> "DE"
      - "EU-Parlament …" / "Europaparlament …" -> "EU"
      - "<State> Wahl YYYY" -> "DE-<code>" using the German state map
      - Fallback -> "unbekannt" (quarantine) + WARNING

    The fallback is a QUARANTINE, not "DE" — an unrecognized label (new
    format, Kommunalwahl) stamped "DE" would MatchAny-match EVERY election
    context and could never be scoped. "unbekannt" matches no real region_path,
    so quarantined chunks are unreachable by retrieval until re-labeled — safe
    by design, and the WARNING makes the gap visible.

    Args:
        period_label: The ``label`` field of a parliament-period record,
                      e.g. ``"Bundestag Wahl 2021"``.

    Returns:
        Scalar region string for Qdrant payload, e.g. ``"DE"`` or ``"DE-BW"``;
        ``"unbekannt"`` for unrecognized labels.
    """
    lower = period_label.strip().lower()
    if lower.startswith("bundestag"):
        return "DE"
    if lower.startswith("eu-parlament") or lower.startswith("europaparlament"):
        return "EU"
    # Try German state prefix: "<State> Wahl YYYY"
    # Sort longest-name-first so the most-specific name wins any prefix collision
    # (e.g. "sachsen-anhalt" before "sachsen" avoids mis-tagging DE-SN for DE-ST).
    for state_name, code in sorted(_STATE_CODE_MAP.items(), key=lambda kv: -len(kv[0])):
        if lower.startswith(state_name):
            return code
    logger.warning(
        "region_for_period: unrecognized parliament-period label %r — quarantining "
        "with region 'unbekannt' (unreachable by retrieval until re-labeled; "
        "add a mapping rule if this is a real election level).",
        period_label,
    )
    return "unbekannt"


def wahlperiode_for_period(period_label: str) -> Optional[int]:
    """Derive the Bundestag Wahlperiode number from a parliament-period label.

    Only Bundestag periods yield a non-None value.

    Args:
        period_label: The ``label`` field of a parliament-period record,
                      e.g. ``"Bundestag Wahl 2021"``.

    Returns:
        Integer Wahlperiode (e.g. 20), or None for non-Bundestag periods.
    """
    lower = period_label.strip().lower()
    if not lower.startswith("bundestag"):
        return None
    # Extract 4-digit year
    match = re.search(r"\b(20\d{2}|19\d{2})\b", period_label)
    if match:
        return _BUNDESTAG_WAHLPERIODE.get(match.group(1))
    return None


def extract_main_text(html: str) -> str:
    """Extract the main article text from a manifesto web page (pure, no network).

    Uses trafilatura's main-content extraction (text-vs-link density + semantic
    heuristics) to isolate the document body and strip boilerplate — navigation,
    headers, footers, cookie banners, share buttons, sidebars — so only the
    manifesto prose is embedded, not site chrome.  Format-agnostic: no per-party
    selectors.

    Pages with no extractable article body (e.g. a "download our program"
    landing page) yield an empty / very short string; the caller's length floor
    then skips them rather than embedding navigation noise.

    Args:
        html: Raw HTML of the fetched page.

    Returns:
        Clean plain-text main content, or "" when nothing substantive is found.
    """
    import trafilatura  # noqa: PLC0415

    extracted = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        favor_recall=True,
    )
    return (extracted or "").strip()


# chunk_pages is centralised in ingestion.chunking (imported above and
# re-exported here for the manifesto connector). Manifestos split per page so
# each chunk's citation #page= anchor lands on the page the passage is on.


def build_manifesto_records(
    program: dict,
    period_date_iso: str,
    chunks: list[tuple[str, Optional[int], Optional[int]]],
    source_kind: SourceKind,
    source_url: Optional[str],
    total_pages: Optional[int] = None,
) -> list[ChunkRecord]:
    """Build ChunkRecord list for one manifesto program (pure, no I/O).

    Constructs the locked payload envelope + source-owned meta for each chunk.
    None-valued meta keys are omitted (build dict, drop None).

    citation_url points directly at the original source (the AW ``file`` PDF URL
    for pdf sources, or the link URI for link sources) — wahl.chat does not
    re-serve or duplicate the file, so the citation resolves to where the
    document actually lives.

    Args:
        program:         AW election-program dict with keys: id, label, party,
                         parliament_period (label field used here).
        period_date_iso: ISO date string from parliament_period election_date
                         (used as publish_date).
        chunks:          List of (text, page_start, page_end) tuples. page_start
                         and page_end may be None for HTML sources.
        source_kind:     ``"pdf"`` or ``"link"``.
        source_url:      Provenance URL (PDF download URL or link URI). PDF
                         chunks cite it with a per-chunk ``#page=`` anchor;
                         link chunks cite it verbatim.
        total_pages:     Total page count (pdf only; None for link sources).

    Returns:
        List of ChunkRecord instances, one per chunk.
    """
    program_id: int = program["id"]
    program_label: str = program.get("label") or ""
    party_label: str = (program.get("party") or {}).get("label") or ""
    period_label: str = (program.get("parliament_period") or {}).get("label") or ""

    party_slug = party_to_slug(party_label)
    region = region_for_period(period_label)
    wahlperiode = wahlperiode_for_period(period_label)

    publish_date = date_type.fromisoformat(period_date_iso)

    sid = compute_source_item_id("party_manifesto", str(program_id))

    citation_title = f"{program_label} – {period_label}"

    parliament_period_id = (program.get("parliament_period") or {}).get("id")

    records: list[ChunkRecord] = []
    total_chunks = len(chunks)
    for chunk_index, (text, page_start, page_end) in enumerate(chunks):
        # Chunk-specific citation: PDF chunks deep-link to the page the passage
        # starts on (pypdf page numbers are 1-based physical PDF pages, so the
        # anchor is exact). Never clobber an existing fragment; link sources
        # keep the plain URI.
        citation_url = source_url
        if (
            source_kind == SourceKind.PDF
            and citation_url
            and page_start
            and "#" not in citation_url
        ):
            citation_url = f"{citation_url}#page={page_start}"

        # Typed meta builder (schemas convention that votes/speeches follow —
        # extra="forbid" rejects typos at build time); exclude_none drops
        # None-valued keys.
        meta: dict = ManifestoMeta(
            aw_program_id=program_id,
            parliament_period_id=parliament_period_id,
            parliament_period_label=period_label,
            source_kind=source_kind,
            source_url=source_url,
            total_pages=total_pages,
            page_start=page_start,
            page_end=page_end,
            total_chunks=total_chunks,
            raw_party_label=party_label if party_slug == "unbekannt" else None,
        ).model_dump(mode="json", exclude_none=True)

        # Change-aware content_hash (mirrors the op mapper): per-chunk text so an
        # updated program text re-writes via run.py's guard; includes the resolved
        # party slug (indexed tenant field) AND the displayed citation/provenance
        # (URL with page anchor, title, source, page window, publish date) — a
        # provenance-only correction must be refreshable, not permanently stale.
        # NOTE: on the connector path the guard only sees already-present
        # programs on MANIFESTO_REFRESH=1 runs (normal discover excludes them
        # via set-difference); bulk.py rewrites each program's footprint
        # unconditionally.
        content_hash = hashlib.sha256(
            json.dumps(
                {
                    "text": text,
                    "party_slug": party_slug,
                    "region": region,
                    "wahlperiode": wahlperiode,
                    "program_id": program_id,
                    "citation_url": citation_url,
                    "citation_title": citation_title,
                    "source_url": source_url,
                    "page_start": page_start,
                    "page_end": page_end,
                    "total_pages": total_pages,
                    "publish_date": period_date_iso,
                },
                sort_keys=True,
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()

        chunk_key = make_chunk_key(sid, chunk_index)
        records.append(
            ChunkRecord(
                chunk_key=chunk_key,
                source_item_id=sid,
                chunk_index=chunk_index,
                text=text,
                party_id=party_slug,
                region=region,
                authority_tier=AuthorityTier.SELF_REPORTED,
                source_type=SourceType.PARTY_MANIFESTO,
                publish_date=publish_date,
                citation_url=citation_url,
                citation_title=citation_title,
                external_id=program_id,
                wahlperiode=wahlperiode,
                content_hash=content_hash,
                meta=meta if meta else None,
            )
        )
    return records

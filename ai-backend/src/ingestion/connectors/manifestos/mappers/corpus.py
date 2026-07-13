# SPDX-FileCopyrightText: 2025 wahl.chat
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
import re
from datetime import date as date_type
from typing import Optional

import tiktoken

from src.ingestion.connectors.abgeordnetenwatch.mappers.corpus import (
    _normalize_fraction_label,
)
from src.ingestion.ids import compute_source_item_id, make_chunk_key
from src.ingestion.schemas import AuthorityTier, ChunkRecord, SourceType

# ---------------------------------------------------------------------------
# Party slug map — for election-program party.label
# ---------------------------------------------------------------------------

# Comprehensive explicit map: normalized-AW-label -> canonical slug.
# Keys are lowercased and invisible-char-stripped (as produced by
# _normalize_fraction_label).  Slugs must match the chat's context slugs for
# the major parties; minor/regional parties get clean derived slugs here so
# that every one of the ~52 AW parties gets a stable, distinct slug rather than
# falling through to "unbekannt".
_MANIFESTO_PARTY_SLUG_MAP: dict[str, str] = {
    # Majors (must match chat context slugs exactly)
    "spd": "spd",
    "cdu": "cdu",
    "cdu/csu": "cdu",
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
    "fraktionslos": "fraktionslos",
    # Regional / smaller parties
    "freie wähler": "fw",
    "ödp": "oedp",
    "volt": "volt",
    "piraten": "piraten",
    "die partei": "die-partei",
    "partei der humanisten": "pdh",
    "partei für verjüngungsforschung": "verjuengung",
    "tierschutzpartei": "tierschutzpartei",
    "diebasis": "basis",
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

# ---------------------------------------------------------------------------
# tiktoken encoder (cached)
# ---------------------------------------------------------------------------

_ENC: Optional[tiktoken.Encoding] = None


def _get_encoding() -> tiktoken.Encoding:
    global _ENC
    if _ENC is None:
        _ENC = tiktoken.get_encoding("cl100k_base")
    return _ENC


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
      1. Normalise the label with ``_normalize_fraction_label`` (strips the
         U+00AD soft hyphen / zero-width chars, collapses whitespace,
         lowercases).  Empty/whitespace-only -> ``"unbekannt"`` immediately.
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
        return "unbekannt"
    normalised = _normalize_fraction_label(label)
    if not normalised:
        return "unbekannt"
    explicit = _MANIFESTO_PARTY_SLUG_MAP.get(normalised)
    if explicit is not None:
        return explicit
    # Derive a slug from the original label (preserves umlaut transliteration
    # that _normalize_fraction_label strips away).
    return _slugify(label)


def region_for_period(period_label: str) -> str:
    """Derive a scalar region code from a parliament-period label.

    Mapping rules:
      - "Bundestag …"  -> "DE"
      - "EU-Parlament …" / "Europaparlament …" -> "EU"
      - "<State> Wahl YYYY" -> "DE-<code>" using the German state map
      - Fallback -> "DE"

    Args:
        period_label: The ``label`` field of a parliament-period record,
                      e.g. ``"Bundestag Wahl 2021"``.

    Returns:
        Scalar region string for Qdrant payload, e.g. ``"DE"`` or ``"DE-BW"``.
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
    return "DE"


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


def chunk_pages(
    pages: list[tuple[int, str]],
    max_tokens: int = 6000,
    overlap: int = 200,
) -> list[tuple[str, int, int]]:
    """Split page-annotated text into token-bounded chunks with overlap.

    Concatenates page texts sequentially, tracking which page numbers each
    chunk spans. A chunk may span multiple pages if a single page's text
    fits within the token budget alongside text from adjacent pages.

    Args:
        pages: List of (page_no, text) tuples (1-indexed page numbers).
        max_tokens: Maximum tokens per chunk (default 6000, well under 8191).
        overlap: Number of tokens to repeat at the start of each subsequent
                 chunk for context continuity (default 200).

    Returns:
        List of (chunk_text, page_start, page_end) tuples. ``page_start`` and
        ``page_end`` are the first/last page numbers whose text appears in the
        chunk. For HTML (pages=[(1, text)]), returns [(text, 1, 1)] when text
        fits in one chunk.
    """
    if not pages:
        return []

    enc = _get_encoding()

    # Build a flat list of (token_ids, page_no) for every page
    # We'll work with token spans and track page boundaries.
    all_tokens: list[int] = []
    # page_boundaries[i] = page_no for the token at position i
    page_of_token: list[int] = []

    for page_no, text in pages:
        if not text:
            continue
        tok = enc.encode(text)
        all_tokens.extend(tok)
        page_of_token.extend([page_no] * len(tok))

    if not all_tokens:
        return []

    if len(all_tokens) <= max_tokens:
        page_start = page_of_token[0]
        page_end = page_of_token[-1]
        return [(enc.decode(all_tokens), page_start, page_end)]

    chunks: list[tuple[str, int, int]] = []
    start = 0
    while start < len(all_tokens):
        end = min(start + max_tokens, len(all_tokens))
        chunk_tokens = all_tokens[start:end]
        page_start = page_of_token[start]
        page_end = page_of_token[end - 1]
        chunks.append((enc.decode(chunk_tokens), page_start, page_end))
        if end == len(all_tokens):
            break
        start = end - overlap

    return chunks


def build_manifesto_records(
    program: dict,
    period_date_iso: str,
    chunks: list[tuple[str, Optional[int], Optional[int]]],
    source_kind: str,
    source_url: Optional[str],
    total_pages: Optional[int] = None,
) -> list[ChunkRecord]:
    """Build ChunkRecord list for one manifesto program (pure, no I/O).

    Constructs the locked payload envelope + source-owned meta for each chunk.
    None-valued meta keys are omitted (build dict, drop None).

    citation_url points directly at the original source (the AW ``file`` PDF URL
    for pdf sources, or the link URI for link sources) — wahl.chat no longer
    re-serves or duplicates the file, so the citation resolves to where the
    document actually lives.

    Args:
        program:         AW election-program dict with keys: id, label, party,
                         parliament_period (label field used here).
        period_date_iso: ISO date string from parliament_period election_date
                         (used as publish_date).
        chunks:          List of (text, page_start, page_end) tuples. page_start
                         and page_end may be None for HTML sources.
        source_kind:     ``"pdf"`` or ``"link"``.
        source_url:      Provenance URL (PDF download URL or link URI). Used
                         verbatim as the citation_url.
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

    # citation_url is the original source URL (external PDF or weblink).
    citation_url = source_url

    citation_title = f"{program_label} – {period_label}"

    records: list[ChunkRecord] = []
    for chunk_index, (text, page_start, page_end) in enumerate(chunks):
        meta: dict = {
            "aw_program_id": program_id,
            "parliament_period_id": (program.get("parliament_period") or {}).get("id"),
            "parliament_period_label": period_label,
            "source_kind": source_kind,
            "source_url": source_url,
        }
        meta["total_pages"] = total_pages
        meta["page_start"] = page_start
        meta["page_end"] = page_end
        if party_slug == "unbekannt":
            meta["raw_party_label"] = party_label

        # Drop None values from meta
        meta = {k: v for k, v in meta.items() if v is not None}

        # Change-aware content_hash (mirrors the op mapper): per-chunk text so an
        # updated program text re-writes via run.py's guard; includes the resolved
        # party slug (indexed tenant field).
        content_hash = hashlib.sha256(
            json.dumps(
                {
                    "text": text,
                    "party_slug": party_slug,
                    "region": region,
                    "wahlperiode": wahlperiode,
                    "program_id": program_id,
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

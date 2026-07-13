# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
AW Q&A HTML scrape -> qa_transcript corpus.

Implements two public functions:
  - scrape_qa(html, profile_slug) — pure HTML parser: parse div.question blocks
    from a saved or live AW Q&A profile page into Q&A pair dicts; skips unanswered
    questions ("Antwort ausstehend" or missing .question__answer div).
  - chunk_qa(source_item, raw) — worker-compatible 2-arg chunker that converts
    a stored Q&A pair into deterministic ChunkRecords for embedding.

Design decisions:
  - chunk_qa has the same 2-arg (source_item, raw) signature as chunk_poll
    and chunk_program (worker-dispatcher contract).
  - ingest_qa stores verbatim Q&A pair bytes to GCS before writing the
    source_item; worker re-loads raw from GCS at chunk time.
  - ingest_qa receives db as an argument — never calls _get_db() itself.
  - db writes use .set() — unconditional overwrite = idempotent upsert.

Security notes:
  HTML injection guard: chunk text is extracted via BeautifulSoup
  get_text() — no raw HTML or script tags are embedded in corpus chunks.
  Verbatim original (HTML bytes) is stored to GCS for audit, never executed.

  Evidence-only invariant: this module does NOT import
  anything from the matcher layer. The STRUCTURAL guarantee is enforced by
  the absence of any stance-pair module imports. The test suite uses
  inspect.getsource() to verify this at CI time.

  Mis-routing guard: QA_TRANSCRIPT is wired to chunk_qa in
  worker.chunk_source_item; a missing-branch regression fails CI.

  GDPR Art. 9 wall: this module does NOT access users/ collection.
  Candidate Q&A answers are public-figure political statements — not
  Art. 9 data about a user. The module never joins to any user document.

  Bounded scrape: scrape_qa processes only the HTML passed in
  (one page); callers manage pagination; date extracted by fixed string split
  on "von" / "•" markers (no catastrophic-backtrack regex).

  No new packages: beautifulsoup4 is already in ai-backend deps.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Any

from bs4 import BeautifulSoup

# gcs.py deleted — qa.py is a deferred module
# (not wired to the active connector pipeline).  gcs is stubbed to None so
# import-time crashes are avoided; ingest_qa() will raise AttributeError
# if called, which is the expected failure mode for a deferred feature.
# This module will be rewritten to ChunkRecord / Qdrant pattern in a future phase.
gcs = None  # type: ignore[assignment]  # deferred module: gcs.py deleted
from src.ingestion.ids import compute_source_item_id, make_chunk_key  # noqa: E402
try:
    from src.ingestion.schemas import (  # type: ignore[attr-defined]
        AuthorityTier,
        ChunkRecord,
        SourceItemRecord,
        SourceType,
    )
except ImportError:
    AuthorityTier = None  # type: ignore[assignment, misc]
    ChunkRecord = None  # type: ignore[assignment, misc]
    SourceItemRecord = None  # type: ignore[assignment, misc]
    SourceType = None  # type: ignore[assignment, misc]

logger = logging.getLogger(__name__)

# A valid AW profile slug is lowercase alphanumerics and hyphens only.
# Anything else (``/``, ``.``, ``%``, whitespace) is a path-traversal / injection
# risk in the pinned profile URL and is rejected before the URL is built.
_PROFILE_SLUG_RE = re.compile(r"^[a-z0-9-]+$")

# ---------------------------------------------------------------------------
# Chunking constants (mirrors programs.py — deterministic, no LLM, no wall-clock)
# ---------------------------------------------------------------------------

# Fixed-size character window for splitting Q&A text into chunks.
# A Q&A pair is typically well under 1500 chars, so most pairs are one chunk.
_CHUNK_SIZE = 1500
# Overlap between consecutive windows for long answers.
_CHUNK_OVERLAP = 150

# Marker that identifies an unanswered question in .answer__header-text text.
_UNANSWERED_MARKER = "Antwort ausstehend"

# HTTP fetch timeout (seconds) for live page requests.
_HTTP_TIMEOUT = 30


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scrape_qa(html: str, profile_slug: str) -> list[dict]:
    """Parse Q&A pair dicts from an AW profile fragen-antworten HTML page.

    Pure HTML parser — no I/O, no side effects.  Callers supply the HTML string
    (from a live fetch or a saved fixture).  This function extracts answered Q&A
    pairs from ``<div class="question">`` blocks using the CSS selectors below.

    CSS selectors used:
      - Question text: ``.question__question a.h4``
      - Questioner + date: ``.question__question-meta`` text (pattern "von [Name] • [date]")
      - Answer body: ``.answer__body`` paragraphs (get_text — no raw HTML)
      - Answer date: ``.answer__header-text`` text (pattern "Antwort [date] von [Name]")
      - Skip: ``.question__answer`` absent OR ``.answer__header-text`` contains
        "Antwort ausstehend"

    Args:
        html:         HTML page content as a string (one AW profile page).
        profile_slug: Politician slug (e.g. "tobias-lindner") — embedded in each
                      returned pair dict for external_id construction.

    Returns:
        List of dicts, one per answered Q&A pair, with keys:
          - profile_slug: str
          - question_slug: str  (last path segment of the question link href)
          - question_text: str
          - questioner: str     (may be empty if meta format does not match)
          - q_date: str         (DD.MM.YYYY — raw extracted string)
          - answer_text: str
          - a_date: str         (DD.MM.YYYY — raw extracted string)
        Unanswered questions are omitted.
    """
    soup = BeautifulSoup(html, "html.parser")
    question_divs = soup.select("div.question")

    pairs: list[dict] = []

    for div in question_divs:
        # ----------------------------------------------------------------
        # Check for .question__answer — absent means unanswered
        # ----------------------------------------------------------------
        answer_div = div.select_one("div.question__answer")
        if answer_div is None:
            logger.debug("scrape_qa: skipping question block with no .question__answer div")
            continue

        # ----------------------------------------------------------------
        # Check for "Antwort ausstehend" marker in header text
        # ----------------------------------------------------------------
        header_text_el = answer_div.select_one(".answer__header-text")
        header_text = header_text_el.get_text(strip=True) if header_text_el else ""
        if _UNANSWERED_MARKER in header_text:
            logger.debug("scrape_qa: skipping unanswered question ('%s')", _UNANSWERED_MARKER)
            continue

        # ----------------------------------------------------------------
        # Question text from .question__question a.h4
        # ----------------------------------------------------------------
        question_link = div.select_one(".question__question a.h4")
        question_text = question_link.get_text(strip=True) if question_link else ""

        # ----------------------------------------------------------------
        # Question slug from href: /profile/<slug>/fragen-antworten/<question-slug>
        # ----------------------------------------------------------------
        question_slug = ""
        if question_link and question_link.get("href"):
            href: str = str(question_link["href"])
            question_slug = href.rstrip("/").split("/")[-1]

        # ----------------------------------------------------------------
        # Questioner + date from .question__question-meta text
        # Pattern: "Frage von [Name] • [DD.MM.YYYY]"  (fixed split)
        # ----------------------------------------------------------------
        questioner = ""
        q_date = ""
        meta_el = div.select_one(".question__question-meta")
        if meta_el:
            meta_text = meta_el.get_text(separator=" ", strip=True)
            # Extract "von [Name] • [date]" — split on " • " first
            if "•" in meta_text:
                before_dot, after_dot = meta_text.split("•", 1)
                q_date = after_dot.strip()
                # Name is the text after "von " (case-insensitive split)
                von_lower = before_dot.lower()
                von_idx = von_lower.rfind(" von ")
                if von_idx != -1:
                    questioner = before_dot[von_idx + 5:].strip()

        # ----------------------------------------------------------------
        # Answer body text from .answer__body paragraphs (get_text)
        # ----------------------------------------------------------------
        answer_body_el = answer_div.select_one(".answer__body")
        answer_text = ""
        if answer_body_el:
            paragraphs = answer_body_el.find_all("p")
            if paragraphs:
                answer_text = "\n\n".join(
                    p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)
                )
            else:
                # Fallback: get_text on the whole body element
                answer_text = answer_body_el.get_text(separator="\n", strip=True)

        # ----------------------------------------------------------------
        # Answer date from .answer__header-text
        # Pattern: "Antwort [DD.MM.YYYY] von [Name]"  (fixed split)
        # ----------------------------------------------------------------
        a_date = ""
        if header_text:
            # Split on "von " to separate date from politician name
            # "Antwort 15.01.2022 von Tobias Lindner" -> "15.01.2022 von"
            parts = header_text.split()
            # Find the date token (format DD.MM.YYYY) after "Antwort"
            for i, token in enumerate(parts):
                if len(token) == 10 and token.count(".") == 2:
                    a_date = token
                    break

        pairs.append(
            {
                "profile_slug": profile_slug,
                "question_slug": question_slug,
                "question_text": question_text,
                "questioner": questioner,
                "q_date": q_date,
                "answer_text": answer_text,
                "a_date": a_date,
            }
        )

    return pairs


def ingest_qa(
    db: Any,
    fetch: Any,
    profile_slugs: list[str],
    bucket: str,
    party_id: str = "unbekannt",
    region: str = "DE",
    region_path: list[str] | None = None,
) -> list[SourceItemRecord]:
    """Fetch AW Q&A profile pages and write qa_transcript corpus items.

    For each politician slug in ``profile_slugs``, fetches the answered Q&A
    page (`/profile/<slug>/fragen-antworten?answer=answered`), parses it with
    ``scrape_qa``, and writes one ``SourceItemRecord`` per answered pair.

    Each Q&A pair is:
    1. Stored verbatim to GCS as a JSON payload (idempotent overwrite).
    2. Written as a ``SourceItemRecord`` (source_type=QA_TRANSCRIPT,
       authority_tier=SELF_REPORTED, vector_status="pending") to source_items/
       keyed by its deterministic source_item_id (.set()).

    Zero stance-pair documents are written (structural guarantee — no
    stance-pair modules are imported or called in this module).

    Security:
        ``profile_slugs`` is the trust boundary.  Each slug is validated against
        ``^[a-z0-9-]+$`` BEFORE the pinned profile URL is built; slugs containing
        ``/``, ``.``, ``%``, or whitespace (path-traversal / injection vectors)
        are skipped with a warning.  The injected ``fetch`` callable MUST enforce
        host pinning and ``allow_redirects=False`` — building the URL from a
        pinned host is not sufficient if ``fetch`` follows redirects.

    Args:
        db:            Firestore client handle (passed by caller).
        fetch:         Callable(url: str) -> str that returns HTML for the URL.
                       Pass an AW-paced fetch function for live use.  The callable
                       MUST enforce host pinning + ``allow_redirects=False``; do
                       NOT wire a bare ``requests.get`` (it follows redirects).
                       Must return the page HTML as text.
        profile_slugs: List of AW politician slugs (e.g. ["tobias-lindner"]).
                       Each must match ``^[a-z0-9-]+$`` or it is skipped.
        bucket:        GCS bucket name for storage_ref construction.
        party_id:      Party slug for the SourceItemRecord (default "unbekannt" if
                       caller does not know the party at ingest time).
        region:        Region scalar (default "DE").
        region_path:   Region path (default ["EU", "DE"]).

    Returns:
        List of ``SourceItemRecord`` instances written to Firestore.
    """
    if region_path is None:
        region_path = ["EU", "DE"]

    written: list[SourceItemRecord] = []

    for slug in profile_slugs:
        # Validate the slug before interpolating it into the pinned URL.
        if not isinstance(slug, str) or not _PROFILE_SLUG_RE.match(slug):
            logger.warning(
                "qa: skipping invalid profile slug=%r (must match ^[a-z0-9-]+$ — "
                "rejects '/', '.', '%%', whitespace; WR-04 path-traversal guard)",
                slug,
            )
            continue

        url = f"https://www.abgeordnetenwatch.de/profile/{slug}/fragen-antworten?answer=answered"

        try:
            html: str = fetch(url)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "qa: failed to fetch profile url=%s error=%s",
                url,
                str(exc)[:200],
            )
            continue

        pairs = scrape_qa(html, slug)

        for pair in pairs:
            question_slug = pair.get("question_slug") or "unknown"
            external_id = f"aw_qa:{slug}:{question_slug}"
            source_item_id = compute_source_item_id("qa_transcript", external_id)

            # ----------------------------------------------------------------
            # Parse publish date from answer date string (DD.MM.YYYY)
            # Fixed split on "." — no regex
            # publish_date is required and the corpus must be deterministic;
            # skip-and-warn a date-less pair rather than fabricating date.today().
            # ----------------------------------------------------------------
            publish_date = _parse_qa_date(pair.get("a_date") or pair.get("q_date") or "")
            if publish_date is None:
                logger.warning(
                    "qa: skipping pair slug=%s question_slug=%s — unparseable date "
                    "(a_date=%r q_date=%r; publish_date is required, not fabricating "
                    "date.today() — WR-07)",
                    slug,
                    question_slug,
                    pair.get("a_date"),
                    pair.get("q_date"),
                )
                continue

            # ----------------------------------------------------------------
            # Store verbatim raw pair to GCS (idempotent overwrite)
            # ----------------------------------------------------------------
            raw_bytes: bytes = json.dumps(pair, ensure_ascii=False).encode("utf-8")
            blob_path = f"aw_qa/{slug}/{question_slug}.json"
            storage_ref: str = gcs.store_original(blob_path, raw_bytes, "application/json")  # type: ignore[attr-defined]

            # ----------------------------------------------------------------
            # Build SourceItemRecord and write to source_items/ (.set())
            # ----------------------------------------------------------------
            source_item = SourceItemRecord(
                source_item_id=source_item_id,
                source_type=SourceType.QA_TRANSCRIPT,
                external_id=external_id,
                party_id=party_id,
                region=region,
                region_path=region_path,
                authority_tier=AuthorityTier.SELF_REPORTED,
                publish_date=publish_date,
                storage_ref=storage_ref,
                vector_status="pending",
            )
            db.collection("source_items").document(str(source_item_id)).set(
                source_item.model_dump(mode="json")
            )
            written.append(source_item)
            logger.info(
                "qa: wrote qa_transcript source_item source_item_id=%s slug=%s question_slug=%s",
                source_item_id,
                slug,
                question_slug,
            )

    return written


def chunk_qa(source_item: SourceItemRecord, raw: dict) -> list[ChunkRecord]:
    """Produce deterministic ChunkRecords from a stored Q&A pair.

    This is the WORKER's chunker for QA_TRANSCRIPT items.  It has the SAME
    2-arg ``(source_item, raw)`` signature as ``chunk_poll`` and ``chunk_program``
    (worker-dispatcher contract).

    The Q&A pair text (question + answer) is concatenated and split into
    fixed-size character windows with a small overlap.  Splitting is deterministic
    (no LLM, no wall-clock) so re-running with the same input always yields the
    same chunk keys (idempotency).

    Text extraction uses string concatenation only — no BeautifulSoup required
    here because the raw payload already contains plain text (HTML was
    stripped by scrape_qa's get_text calls before storage).

    Empty text produces an empty list (not an error).

    Args:
        source_item: The normalised ``SourceItemRecord`` for the Q&A pair.
                     Must have ``source_item_id``, ``region``,
                     ``authority_tier``, ``source_type``, and ``publish_date``.
        raw:         The GCS-stored raw payload dict with keys ``question_text``
                     and ``answer_text`` (plain text, HTML-stripped at scrape time).

    Returns:
        A list of ``ChunkRecord`` instances with zero-based sequential indexes.
        Returns ``[]`` for empty or whitespace-only Q&A text.
    """
    question_text: str = raw.get("question_text") or ""
    answer_text: str = raw.get("answer_text") or ""

    # Combine Q+A into a single plain-text block for chunking
    combined = ""
    if question_text.strip():
        combined += f"Frage: {question_text.strip()}"
    if answer_text.strip():
        if combined:
            combined += "\n\nAntwort: "
        combined += answer_text.strip()

    text = combined.strip()
    if not text:
        return []

    # Fixed-size character windows with overlap (deterministic, no regex, no LLM)
    windows: list[str] = []
    start = 0
    while start < len(text):
        end = start + _CHUNK_SIZE
        window = text[start:end].strip()
        if window:
            windows.append(window)
        start += _CHUNK_SIZE - _CHUNK_OVERLAP

    chunks: list[ChunkRecord] = []
    for chunk_index, window_text in enumerate(windows):
        chunk_key = make_chunk_key(source_item.source_item_id, chunk_index)
        # Build citation URL from profile_slug and question_slug in raw
        citation_url: str | None = None
        profile_slug = raw.get("profile_slug") or ""
        question_slug = raw.get("question_slug") or ""
        if profile_slug and question_slug:
            citation_url = (
                f"https://www.abgeordnetenwatch.de/profile/{profile_slug}"
                f"/fragen-antworten/{question_slug}"
            )

        chunks.append(
            ChunkRecord(
                chunk_key=chunk_key,
                source_item_id=source_item.source_item_id,
                chunk_index=chunk_index,
                text=window_text,
                party_id=source_item.party_id,
                region=source_item.region,
                authority_tier=source_item.authority_tier,
                source_type=source_item.source_type,
                publish_date=source_item.publish_date,
                citation_url=citation_url,
                citation_title=None,
            )
        )

    return chunks


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_qa_date(date_str: str) -> date | None:
    """Parse a DD.MM.YYYY date string into a date object.

    Uses fixed string split on "." only — no regex, no strptime
    format that could cause backtracking.

    Returns ``None`` on parse failure (never fabricates date.today()).
    The caller skip-and-warns date-less pairs so the corpus stays deterministic.

    Args:
        date_str: Date string in "DD.MM.YYYY" format (e.g. "15.01.2022").

    Returns:
        Parsed date, or ``None`` on parse failure.
    """
    try:
        parts = date_str.strip().split(".")
        if len(parts) == 3:
            day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
            return date(year, month, day)
    except (ValueError, TypeError, IndexError):
        pass
    return None

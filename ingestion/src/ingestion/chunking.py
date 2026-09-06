# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Shared text chunking for ingestion connectors.

One boundary-aware splitter (langchain ``RecursiveCharacterTextSplitter``) so
every connector chunks the same way. Character-based and separator-aware: it
splits on paragraph/sentence boundaries and falls back to smaller separators
only when needed, rather than cutting mid-token. This matches the splitter the
V1 pipeline used for manifesto PDFs and avoids the mid-character slices a raw
token splitter produces (which needed U+FFFD clean-up).

Defaults: 1000 characters with 150 overlap (~15%, within the commonly
recommended 10-20% band). Connectors may override the size/overlap; vote
records are not chunked at all (one record = one chunk).
"""

from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter

# Character-based defaults (not tokens). ~1000 chars keeps chunks well under the
# embedding model's token limit while staying focused enough for retrieval.
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150


def make_splitter(
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> RecursiveCharacterTextSplitter:
    """Build a boundary-aware character splitter with the given bounds."""
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        is_separator_regex=False,
    )


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Split *text* into boundary-aware character chunks.

    Empty/whitespace-only input returns ``[]``; text that fits in one chunk is
    returned as a single-element list.
    """
    if not text or not text.strip():
        return []
    return make_splitter(chunk_size, chunk_overlap).split_text(text)


def chunk_pages(
    pages: list[tuple[int, str]],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[tuple[str, int, int]]:
    """Split page-annotated text, keeping each chunk within a single page.

    Each page's text is split independently (mirroring V1's
    ``split_documents(pages)``), so a chunk never straddles a page boundary and
    its citation deep-link anchor (``#page=page_start``) always lands on the
    page the quoted passage is actually on. For single-"page" inputs (HTML,
    ``pages=[(1, text)]``) every chunk is attributed to page 1.

    Returns ``(chunk_text, page_start, page_end)`` tuples; ``page_start`` and
    ``page_end`` are equal because chunks are per-page.
    """
    splitter = make_splitter(chunk_size, chunk_overlap)
    out: list[tuple[str, int, int]] = []
    for page_no, text in pages:
        if not text or not text.strip():
            continue
        for chunk in splitter.split_text(text):
            out.append((chunk, page_no, page_no))
    return out

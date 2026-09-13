# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Tests for the shared ingestion chunker (ingestion.chunking).

Boundary-aware character splitting via langchain RecursiveCharacterTextSplitter:
short text stays whole, long text splits with overlap, and page-annotated text
is split per page so a chunk never straddles a page boundary.
"""

from ingestion.chunking import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    chunk_pages,
    chunk_text,
)


class TestChunkText:
    def test_empty_and_whitespace_return_empty(self) -> None:
        assert chunk_text("") == []
        assert chunk_text("   \n\t ") == []

    def test_short_text_single_chunk(self) -> None:
        text = "Ein kurzer Satz."
        assert chunk_text(text) == [text]

    def test_long_text_splits_into_nonempty_chunks(self) -> None:
        text = " ".join(f"Satz Nummer {i} mit Inhalt." for i in range(300))
        chunks = chunk_text(text, chunk_size=200, chunk_overlap=20)
        assert len(chunks) > 1
        assert all(c.strip() for c in chunks)

    def test_more_overlap_never_fewer_chunks(self) -> None:
        text = " ".join(f"wort{i}" for i in range(400))
        none = chunk_text(text, chunk_size=200, chunk_overlap=0)
        some = chunk_text(text, chunk_size=200, chunk_overlap=60)
        assert len(some) >= len(none)

    def test_defaults_are_character_based(self) -> None:
        assert DEFAULT_CHUNK_SIZE == 1000
        assert DEFAULT_CHUNK_OVERLAP == 150


class TestChunkPages:
    def test_empty_returns_empty(self) -> None:
        assert chunk_pages([]) == []

    def test_blank_pages_skipped(self) -> None:
        assert chunk_pages([(1, "  "), (2, "")]) == []

    def test_each_chunk_stays_within_one_page(self) -> None:
        pages = [(1, "Seite eins."), (2, "Seite zwei.")]
        result = chunk_pages(pages)
        assert {(ps, pe) for _, ps, pe in result} == {(1, 1), (2, 2)}

    def test_long_page_splits_but_keeps_its_page_number(self) -> None:
        result = chunk_pages([(7, "Wort " * 500)], chunk_size=200, chunk_overlap=20)
        assert len(result) > 1
        for _, ps, pe in result:
            assert ps == 7 and pe == 7

    def test_html_single_block_is_page_one(self) -> None:
        result = chunk_pages([(1, "HTML-Text. " * 200)], chunk_size=200)
        assert result
        assert all(ps == 1 and pe == 1 for _, ps, pe in result)

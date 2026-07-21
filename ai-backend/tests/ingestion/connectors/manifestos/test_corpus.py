# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Unit tests for src/ingestion/connectors/manifestos/mappers/corpus.py.

Tests are pure (no network, no OpenAI, no Qdrant, no Firestore): they cover
only the deterministic helper functions:
  (a) party_to_slug   — all known parties + soft-hyphen Greens + unknown
  (b) region_for_period — Bundestag, EU, states, fallback
  (c) wahlperiode_for_period — Bundestag years, non-Bundestag
  (d) chunk_pages     — single page, multi-page over max_tokens, page spans
  (e) build_manifesto_records — pdf program, link program, unknown party
"""

from __future__ import annotations

from datetime import date

import pytest

from src.ingestion.connectors.manifestos.mappers.corpus import (
    _slugify,
    build_manifesto_records,
    chunk_pages,
    extract_main_text,
    party_to_slug,
    region_for_period,
    wahlperiode_for_period,
)
from src.ingestion.schemas import AuthorityTier, SourceType


# ===========================================================================
# (a) party_to_slug
# ===========================================================================


class TestPartyToSlug:
    """party_to_slug maps all known AW party labels to canonical slugs."""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("SPD", "spd"),
            ("spd", "spd"),
            ("CDU", "cdu"),
            ("CSU", "csu"),
            ("FDP", "fdp"),
            ("AfD", "afd"),
            ("afd", "afd"),
            ("BSW", "bsw"),
            ("bsw", "bsw"),
            ("Fraktionslos", "fraktionslos"),
            # Standard ASCII Greens label
            ("BÜNDNIS 90/DIE GRÜNEN", "gruene"),
            ("bündnis 90/die grünen", "gruene"),
            ("Die Grünen", "gruene"),
            ("grüne", "gruene"),
            # Linke variants
            ("DIE LINKE", "linke"),
            ("Die Linke.", "linke"),
            ("Linke", "linke"),
            # Explicit map — smaller parties
            ("FREIE WÄHLER", "fw"),
            ("ÖDP", "oedp"),
            ("Die PARTEI", "die-partei"),
            ("dieBasis", "basis"),
            ("Partei der Humanisten", "pdh"),
            # Explicit map — Piraten / Volt now have entries
            ("Piraten", "piraten"),
            ("Volt", "volt"),
            # Fallback via _slugify — not in explicit map
            ("Klimaliste", "klimaliste"),
            ("Tierschutz hier!", "tierschutz-hier"),
            # Missing / empty
            (None, "unbekannt"),
            ("", "unbekannt"),
        ],
    )
    def test_known_and_unknown(self, raw: str | None, expected: str) -> None:
        assert party_to_slug(raw) == expected

    def test_soft_hyphen_greens(self) -> None:
        """U+00AD soft hyphen in 'BÜNDNIS 90/­DIE GRÜNEN' must resolve to gruene."""
        # This is the exact label AW embeds in the 20th/21st Bundestag Greens fraction
        label_with_soft_hyphen = "BÜNDNIS 90/­DIE GRÜNEN"
        assert party_to_slug(label_with_soft_hyphen) == "gruene"

    def test_unknown_party_derives_slug_via_slugify(self) -> None:
        """A party not in the explicit map gets a clean derived slug (not 'unbekannt')."""
        assert party_to_slug("Klimaliste Sachsen") == "klimaliste-sachsen"

    def test_empty_string_returns_unbekannt(self) -> None:
        assert party_to_slug("") == "unbekannt"

    def test_none_returns_unbekannt(self) -> None:
        assert party_to_slug(None) == "unbekannt"


# ===========================================================================
# (_slugify helper)
# ===========================================================================


class TestSlugify:
    """_slugify produces clean ASCII slugs with umlaut transliteration."""

    @pytest.mark.parametrize(
        "text, expected",
        [
            ("Volt", "volt"),
            ("Klimaliste", "klimaliste"),
            ("Freie Sachsen", "freie-sachsen"),
            ("Tierschutz hier!", "tierschutz-hier"),
            ("Sozialistische Gleichheitspartei", "sozialistische-gleichheitspartei"),
            # Umlaut transliteration
            ("Ödnis", "oednis"),
            ("Überparteilich", "ueberparteilich"),
            ("Grüne", "gruene"),
            ("Größe", "groesse"),
            # Punctuation collapse / suffix stripping
            ("MERA25", "mera25"),
            # U+00B3 superscript-3 is not [a-z0-9], gets replaced then stripped
            ("Volt³", "volt"),
            # Already clean
            ("fdp", "fdp"),
        ],
    )
    def test_slugify_output(self, text: str, expected: str) -> None:
        assert _slugify(text) == expected

    def test_empty_string_returns_unbekannt(self) -> None:
        assert _slugify("") == "unbekannt"

    def test_punctuation_only_returns_unbekannt(self) -> None:
        assert _slugify("!!!") == "unbekannt"


# ===========================================================================
# (b) region_for_period
# ===========================================================================


class TestRegionForPeriod:
    """region_for_period maps parliament-period labels to scalar region codes."""

    @pytest.mark.parametrize(
        "label, expected",
        [
            ("Bundestag Wahl 2021", "DE"),
            ("Bundestag Wahl 2025", "DE"),
            ("Bundestag 2017 - 2021", "DE"),
            ("EU-Parlament Wahl 2024", "EU"),
            ("Europaparlament Wahl 2019", "EU"),
            ("Bayern Wahl 2023", "DE-BY"),
            ("Baden-Württemberg Wahl 2021", "DE-BW"),
            ("Berlin Wahl 2023", "DE-BE"),
            ("Hamburg Wahl 2020", "DE-HH"),
            ("Nordrhein-Westfalen Wahl 2022", "DE-NW"),
            ("Thüringen Wahl 2024", "DE-TH"),
            ("Sachsen Wahl 2024", "DE-SN"),
            # Regression: Sachsen-Anhalt must NOT match the shorter "sachsen" prefix (insertion-order bug)
            ("Sachsen-Anhalt Wahl 2021", "DE-ST"),
            # unrecognized labels are QUARANTINED, not stamped "DE" —
            # region "DE" would MatchAny-match every context; "unbekannt"
            # matches none, so the chunk is unreachable until re-labeled.
            ("Kommunalwahl München 2026", "unbekannt"),
            ("Unbekanntes Parlament", "unbekannt"),
        ],
    )
    def test_region_mapping(self, label: str, expected: str) -> None:
        assert region_for_period(label) == expected

    def test_unknown_label_quarantine_warns(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """the quarantine fallback must log a WARNING so the gap is visible."""
        import logging

        from src.ingestion.connectors.manifestos.mappers import corpus as corpus_mod

        with caplog.at_level(logging.WARNING, logger=corpus_mod.logger.name):
            assert region_for_period("Völlig Unbekanntes Gremium 2030") == "unbekannt"
        assert any("unbekannt" in r.message for r in caplog.records)

    def test_de_only_for_bundestag_labels(self) -> None:
        """'DE' is reserved for labels starting with 'bundestag'."""
        assert region_for_period("Bundestag Wahl 2029") == "DE"
        assert region_for_period("Irgendein Bundes-Gremium") == "unbekannt"


# ===========================================================================
# (c) wahlperiode_for_period
# ===========================================================================


class TestWahlperiodeForPeriod:
    """wahlperiode_for_period maps Bundestag election years to period numbers."""

    @pytest.mark.parametrize(
        "label, expected",
        [
            ("Bundestag Wahl 2017", 19),
            ("Bundestag Wahl 2021", 20),
            ("Bundestag Wahl 2025", 21),
            ("Bundestag 2021 - 2025", 20),
            # Non-Bundestag -> None
            ("EU-Parlament Wahl 2024", None),
            ("Bayern Wahl 2023", None),
            ("Berlin Wahl 2021", None),
            # Bundestag with unknown year -> None
            ("Bundestag Wahl 1998", None),
        ],
    )
    def test_wahlperiode(self, label: str, expected: int | None) -> None:
        assert wahlperiode_for_period(label) == expected


# ===========================================================================
# extract_main_text — trafilatura main-content extraction
# ===========================================================================


_HTML_WITH_BOILERPLATE = """
<!DOCTYPE html>
<html lang="de">
  <head><title>Wahlprogramm</title></head>
  <body>
    <nav><a href="/">Startseite</a> <a href="/spenden">JETZT SPENDEN</a></nav>
    <header>Cookie-Hinweis: Diese Seite verwendet Cookies. Akzeptieren</header>
    <article>
      <h1>Unser Wahlprogramm 2025</h1>
      <p>Wir setzen uns für bezahlbaren Wohnraum ein. Jeder Mensch hat ein Recht
      auf eine sichere und finanzierbare Wohnung, und wir werden den sozialen
      Wohnungsbau massiv ausbauen und Mietpreisbremsen konsequent durchsetzen.</p>
      <p>Klimaschutz ist die zentrale Aufgabe unserer Zeit. Wir investieren in
      erneuerbare Energien, den öffentlichen Nahverkehr und eine klimaneutrale
      Industrie, damit Deutschland seine Klimaziele erreicht.</p>
    </article>
    <footer>Impressum | Datenschutz | Folgen Sie uns auf Twitter</footer>
  </body>
</html>
"""


class TestExtractMainText:
    """extract_main_text isolates article body and drops site boilerplate."""

    def test_keeps_main_content(self) -> None:
        text = extract_main_text(_HTML_WITH_BOILERPLATE)
        assert "bezahlbaren Wohnraum" in text
        assert "erneuerbare Energien" in text

    def test_strips_boilerplate(self) -> None:
        text = extract_main_text(_HTML_WITH_BOILERPLATE)
        assert "JETZT SPENDEN" not in text
        assert "Cookie-Hinweis" not in text
        assert "Impressum" not in text

    def test_empty_html_returns_empty(self) -> None:
        assert extract_main_text("") == ""

    def test_no_article_body_returns_short_or_empty(self) -> None:
        # A nav-only landing page has no extractable article — caller's length
        # floor then skips it rather than embedding navigation noise.
        nav_only = "<html><body><nav><a href='/'>Home</a></nav></body></html>"
        assert len(extract_main_text(nav_only)) < 500


# ===========================================================================
# (d) chunk_pages
# ===========================================================================


class TestChunkPages:
    """chunk_pages splits page-annotated text into token-bounded chunks."""

    def test_empty_pages_returns_empty(self) -> None:
        assert chunk_pages([]) == []

    def test_single_page_short_text_one_chunk(self) -> None:
        result = chunk_pages([(1, "Dies ist ein kurzer Text.")])
        assert len(result) == 1
        chunk_text, page_start, page_end = result[0]
        assert "kurzer Text" in chunk_text
        assert page_start == 1
        assert page_end == 1

    def test_html_single_block_page_1_1(self) -> None:
        """HTML source passes pages=[(1, text)]; result must have page_start=page_end=1."""
        text = "Ein langer HTML-Text " * 50
        result = chunk_pages([(1, text)])
        assert len(result) >= 1
        for _, ps, pe in result:
            assert ps == 1
            assert pe == 1

    def test_multi_page_fits_in_one_chunk(self) -> None:
        """Two short pages -> one chunk spanning page 1 to page 2."""
        pages = [(1, "Seite eins Text."), (2, "Seite zwei Text.")]
        result = chunk_pages(pages)
        assert len(result) == 1
        _, page_start, page_end = result[0]
        assert page_start == 1
        assert page_end == 2

    def test_multi_page_over_max_tokens_splits(self) -> None:
        """Many pages exceeding max_tokens must produce multiple chunks."""
        # Create ~12000 tokens worth of text across 10 pages
        # Each token is roughly one word; 'word ' is about 1 token
        long_page_text = "wort " * 1500  # ~1500 tokens per page
        pages = [(i, long_page_text) for i in range(1, 9)]
        result = chunk_pages(pages, max_tokens=6000, overlap=200)
        assert len(result) > 1

    def test_chunk_page_spans_are_correct(self) -> None:
        """page_start / page_end must accurately reflect which pages tokens came from."""
        # Build pages such that page 1 and 2 fit in the first chunk,
        # and page 3+ overflow into subsequent chunks.
        page_text = "token " * 2500  # ~2500 tokens per page
        pages = [(i, page_text) for i in range(1, 5)]  # 4 pages = ~10000 tokens
        result = chunk_pages(pages, max_tokens=6000, overlap=0)
        # First chunk should start on page 1
        assert result[0][1] == 1
        # Last chunk should end on page 4
        assert result[-1][2] == 4
        # Chunks should be contiguous (page_end of chunk N >= page_start of chunk N+1 - 1)
        for i in range(len(result) - 1):
            _, _, pe = result[i]
            _, ps, _ = result[i + 1]
            assert ps <= pe + 1, f"Gap between chunk {i} (end {pe}) and chunk {i+1} (start {ps})"


# ===========================================================================
# (e) build_manifesto_records
# ===========================================================================

_PDF_PROGRAM = {
    "id": 598,
    "label": "Wahlprogramm SPD 2025",
    "party": {"id": 1, "label": "SPD"},
    "parliament_period": {
        "id": 111,
        "label": "Bundestag Wahl 2025",
        "api_url": "https://example.com/api/v2/parliament-periods/111",
    },
    "link": [],
    "file": "https://example.com/spd-programm-2025.pdf",
}

_LINK_PROGRAM = {
    "id": 701,
    "label": "Wahlprogramm Grüne Berlin 2023",
    "party": {"id": 5, "label": "BÜNDNIS 90/DIE GRÜNEN"},
    "parliament_period": {
        "id": 200,
        "label": "Berlin Wahl 2023",
        "api_url": "https://example.com/api/v2/parliament-periods/200",
    },
    "link": [{"uri": "https://gruene-berlin.de/programm", "title": "Programm"}],
    "file": None,
}

_UNKNOWN_PARTY_PROGRAM = {
    "id": 999,
    "label": "Programm Partei XYZ 2025",
    # Use a label whose _slugify output is "unbekannt" (all non-ASCII, non-alnum)
    # so the party_id field is "unbekannt" and raw_party_label appears in meta.
    "party": {"id": 42, "label": "!!!"},
    "parliament_period": {
        "id": 111,
        "label": "Bundestag Wahl 2025",
        "api_url": "https://example.com/api/v2/parliament-periods/111",
    },
    "link": [],
    "file": "https://example.com/xyz.pdf",
}


def _simple_chunks(n: int = 2) -> list[tuple[str, int, int]]:
    return [(f"Text chunk {i} " * 20, i, i) for i in range(1, n + 1)]


def _link_chunks(n: int = 1) -> list[tuple[str, None, None]]:
    return [(f"HTML text chunk {i} " * 20, None, None) for i in range(1, n + 1)]


class TestBuildManifestoRecords:
    """build_manifesto_records produces correctly-shaped ChunkRecord instances."""

    def test_pdf_program_citation_url_is_source_url(self) -> None:
        """PDF program must have citation_url = the original source (AW file) URL.

        wahl.chat no longer re-serves manifesto PDFs, so the citation points at
        the document where it actually lives.
        """
        records = build_manifesto_records(
            program=_PDF_PROGRAM,
            period_date_iso="2025-02-23",
            chunks=_simple_chunks(2),
            source_kind="pdf",
            source_url="https://example.com/spd-programm-2025.pdf",
            total_pages=5,
        )
        assert len(records) == 2
        for rec in records:
            assert rec.citation_url == "https://example.com/spd-programm-2025.pdf"

    def test_pdf_program_source_type_and_authority(self) -> None:
        records = build_manifesto_records(
            program=_PDF_PROGRAM,
            period_date_iso="2025-02-23",
            chunks=_simple_chunks(1),
            source_kind="pdf",
            source_url="https://example.com/spd.pdf",
            total_pages=1,
        )
        rec = records[0]
        assert rec.source_type == SourceType.PARTY_MANIFESTO
        assert rec.authority_tier == AuthorityTier.SELF_REPORTED

    def test_pdf_program_party_id_and_region(self) -> None:
        records = build_manifesto_records(
            program=_PDF_PROGRAM,
            period_date_iso="2025-02-23",
            chunks=_simple_chunks(1),
            source_kind="pdf",
            source_url="https://example.com/spd.pdf",
        )
        rec = records[0]
        assert rec.party_id == "spd"
        assert rec.region == "DE"

    def test_pdf_program_wahlperiode(self) -> None:
        records = build_manifesto_records(
            program=_PDF_PROGRAM,
            period_date_iso="2025-02-23",
            chunks=_simple_chunks(1),
            source_kind="pdf",
            source_url="https://example.com/spd.pdf",
        )
        assert records[0].wahlperiode == 21

    def test_pdf_program_meta_fields(self) -> None:
        records = build_manifesto_records(
            program=_PDF_PROGRAM,
            period_date_iso="2025-02-23",
            chunks=_simple_chunks(2),
            source_kind="pdf",
            source_url="https://example.com/spd.pdf",
            total_pages=3,
        )
        rec = records[0]
        assert rec.meta is not None
        assert rec.meta["source_kind"] == "pdf"
        assert rec.meta["source_url"] == "https://example.com/spd.pdf"
        assert "stored_path" not in rec.meta
        assert rec.meta["total_pages"] == 3
        assert rec.meta["page_start"] == 1
        assert rec.meta["page_end"] == 1
        assert "raw_party_label" not in rec.meta

    def test_pdf_program_meta_has_no_none_values(self) -> None:
        records = build_manifesto_records(
            program=_PDF_PROGRAM,
            period_date_iso="2025-02-23",
            chunks=_simple_chunks(1),
            source_kind="pdf",
            source_url="https://example.com/spd.pdf",
        )
        meta = records[0].meta
        assert meta is not None
        for v in meta.values():
            assert v is not None, f"None value found in meta: {meta}"

    def test_pdf_program_external_id(self) -> None:
        records = build_manifesto_records(
            program=_PDF_PROGRAM,
            period_date_iso="2025-02-23",
            chunks=_simple_chunks(1),
            source_kind="pdf",
            source_url="https://example.com/spd.pdf",
        )
        assert records[0].external_id == 598

    def test_pdf_program_publish_date(self) -> None:
        records = build_manifesto_records(
            program=_PDF_PROGRAM,
            period_date_iso="2025-02-23",
            chunks=_simple_chunks(1),
            source_kind="pdf",
            source_url="https://example.com/spd.pdf",
        )
        assert records[0].publish_date == date(2025, 2, 23)

    def test_link_program_citation_url_is_link_uri(self) -> None:
        """Link program must have citation_url = the link URI."""
        records = build_manifesto_records(
            program=_LINK_PROGRAM,
            period_date_iso="2023-09-10",
            chunks=_link_chunks(1),
            source_kind="link",
            source_url="https://gruene-berlin.de/programm",
        )
        assert len(records) == 1
        assert records[0].citation_url == "https://gruene-berlin.de/programm"

    def test_link_program_source_kind_in_meta(self) -> None:
        records = build_manifesto_records(
            program=_LINK_PROGRAM,
            period_date_iso="2023-09-10",
            chunks=_link_chunks(1),
            source_kind="link",
            source_url="https://gruene-berlin.de/programm",
        )
        meta = records[0].meta
        assert meta is not None
        assert meta["source_kind"] == "link"

    def test_link_program_no_stored_path_in_meta(self) -> None:
        records = build_manifesto_records(
            program=_LINK_PROGRAM,
            period_date_iso="2023-09-10",
            chunks=_link_chunks(1),
            source_kind="link",
            source_url="https://gruene-berlin.de/programm",
        )
        meta = records[0].meta
        assert meta is not None
        assert "stored_path" not in meta

    def test_link_program_page_numbers_none(self) -> None:
        """Link source chunks have page_start=None and page_end=None."""
        records = build_manifesto_records(
            program=_LINK_PROGRAM,
            period_date_iso="2023-09-10",
            chunks=_link_chunks(1),
            source_kind="link",
            source_url="https://gruene-berlin.de/programm",
        )
        meta = records[0].meta
        assert meta is not None
        # page_start and page_end should be absent (None values dropped)
        assert "page_start" not in meta
        assert "page_end" not in meta

    def test_link_program_region_is_state(self) -> None:
        """Berlin period -> region DE-BE."""
        records = build_manifesto_records(
            program=_LINK_PROGRAM,
            period_date_iso="2023-09-10",
            chunks=_link_chunks(1),
            source_kind="link",
            source_url="https://gruene-berlin.de/programm",
        )
        assert records[0].region == "DE-BE"

    def test_unknown_party_raw_party_label_in_meta(self) -> None:
        """When slug == 'unbekannt', meta must contain raw_party_label."""
        records = build_manifesto_records(
            program=_UNKNOWN_PARTY_PROGRAM,
            period_date_iso="2025-02-23",
            chunks=_simple_chunks(1),
            source_kind="pdf",
            source_url="https://example.com/xyz.pdf",
        )
        rec = records[0]
        assert rec.party_id == "unbekannt"
        assert rec.meta is not None
        assert rec.meta.get("raw_party_label") == "!!!"

    def test_chunk_indices_are_sequential(self) -> None:
        records = build_manifesto_records(
            program=_PDF_PROGRAM,
            period_date_iso="2025-02-23",
            chunks=_simple_chunks(5),
            source_kind="pdf",
            source_url="https://example.com/spd.pdf",
        )
        assert [r.chunk_index for r in records] == list(range(5))

    def test_source_item_id_is_stable(self) -> None:
        """Same program_id always yields the same source_item_id."""
        records_a = build_manifesto_records(
            program=_PDF_PROGRAM,
            period_date_iso="2025-02-23",
            chunks=_simple_chunks(1),
            source_kind="pdf",
            source_url="https://example.com/spd.pdf",
        )
        records_b = build_manifesto_records(
            program=_PDF_PROGRAM,
            period_date_iso="2025-02-23",
            chunks=_simple_chunks(1),
            source_kind="pdf",
            source_url="https://example.com/spd.pdf",
        )
        assert records_a[0].source_item_id == records_b[0].source_item_id

    def test_citation_title_format(self) -> None:
        records = build_manifesto_records(
            program=_PDF_PROGRAM,
            period_date_iso="2025-02-23",
            chunks=_simple_chunks(1),
            source_kind="pdf",
            source_url="https://example.com/spd.pdf",
        )
        assert records[0].citation_title == "Wahlprogramm SPD 2025 – Bundestag Wahl 2025"

    def test_content_hash_present_and_change_sensitive(self) -> None:
        """(d) Manifesto chunks stamp a per-chunk content_hash so an updated
        program text re-writes via run.py's change-aware guard."""
        records = build_manifesto_records(
            program=_PDF_PROGRAM,
            period_date_iso="2025-02-23",
            chunks=_simple_chunks(2),
            source_kind="pdf",
            source_url="https://example.com/spd.pdf",
        )
        assert all(r.content_hash is not None for r in records), (
            "every manifesto chunk must stamp content_hash"
        )
        assert records[0].content_hash != records[1].content_hash, (
            "content_hash is per-chunk (different texts → different hashes)"
        )

        changed = build_manifesto_records(
            program=_PDF_PROGRAM,
            period_date_iso="2025-02-23",
            chunks=[("Ganz neuer Programmtext. " * 20, 1, 1)],
            source_kind="pdf",
            source_url="https://example.com/spd.pdf",
        )
        assert changed[0].content_hash != records[0].content_hash, (
            "changing the chunk text must change content_hash"
        )


# ===========================================================================
# manifesto/votes slug-map parity
# ===========================================================================


class TestSlugMapParity:
    """The manifesto map and the AW votes map must be slug-identical for every
    shared label — otherwise manifesto party_id != vote slug != context
    party_id and tenant-filtered manifesto retrieval returns nothing."""

    def test_new_e3_entries_resolve(self) -> None:
        assert party_to_slug("Bürger in Wut") == "biw"
        assert party_to_slug("BVB/Freie Wähler") == "bvb-fw"
        assert party_to_slug("Die Basis") == "basis"
        assert party_to_slug("SSW") == "ssw"

    def test_shared_labels_have_identical_slugs(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.corpus import (
            _AW_FRACTION_SLUG_MAP,
        )
        from src.ingestion.connectors.manifestos.mappers.corpus import (
            _MANIFESTO_PARTY_SLUG_MAP,
        )

        shared = set(_AW_FRACTION_SLUG_MAP) & set(_MANIFESTO_PARTY_SLUG_MAP)
        assert shared, "expected the two maps to share labels"
        mismatches = {
            label: (_AW_FRACTION_SLUG_MAP[label], _MANIFESTO_PARTY_SLUG_MAP[label])
            for label in sorted(shared)
            if _AW_FRACTION_SLUG_MAP[label] != _MANIFESTO_PARTY_SLUG_MAP[label]
        }
        assert not mismatches, (
            "votes map and manifesto map diverge for shared labels "
            f"(label: (votes_slug, manifesto_slug)): {mismatches!r}"
        )


# ===========================================================================
# chunk_pages default budget
# ===========================================================================


def test_chunk_pages_default_max_tokens_is_1500() -> None:
    """the default token budget is 1500 (tight page spans for citation
    deep-links). ~2000 tokens must split under the default (one chunk under
    the old 6000 default)."""
    import inspect

    sig = inspect.signature(chunk_pages)
    assert sig.parameters["max_tokens"].default == 1500

    pages = [(1, "wort " * 1000), (2, "wort " * 1000)]  # ~2000 tokens
    result = chunk_pages(pages)
    assert len(result) > 1, "~2000 tokens must split under the 1500 default"


# ===========================================================================
# U+FFFD stripping at chunk edges
# ===========================================================================


class TestChunkEdgeReplacementChars:
    """A token-boundary slice can split a multi-byte UTF-8 sequence — decode
    then yields U+FFFD at the chunk edges. Edges must be stripped; interior
    replacement chars (genuine source data) are preserved."""

    def test_edges_are_stripped(self) -> None:
        # "🤖" encodes to 3 partial-byte tokens in cl100k_base; max_tokens=2
        # guarantees a chunk boundary inside the character.
        pages = [(1, "Anfang " + "🤖" * 4 + " Ende")]
        chunks = chunk_pages(pages, max_tokens=2, overlap=0)
        assert len(chunks) > 1
        for text, _ps, _pe in chunks:
            assert not text.startswith("�"), f"leading U+FFFD in {text!r}"
            assert not text.endswith("�"), f"trailing U+FFFD in {text!r}"

    def test_interior_replacement_char_preserved(self) -> None:
        # A genuine U+FFFD inside the text must survive chunking untouched.
        pages = [(1, "vorher � nachher")]
        chunks = chunk_pages(pages)
        assert len(chunks) == 1
        assert "�" in chunks[0][0]


# ===========================================================================
# ManifestoMeta typed builder
# ===========================================================================


class TestManifestoMeta:
    def test_extra_fields_forbidden(self) -> None:
        import pydantic
        import pytest as _pytest

        from src.ingestion.connectors.manifestos.mappers.corpus import ManifestoMeta

        with _pytest.raises(pydantic.ValidationError):
            ManifestoMeta(aw_program_id=1, not_a_field="boom")  # type: ignore[call-arg]

    def test_model_dump_drops_none(self) -> None:
        from src.ingestion.connectors.manifestos.mappers.corpus import ManifestoMeta

        dumped = ManifestoMeta(
            aw_program_id=598,
            source_kind="link",
            source_url="https://example.com",
        ).model_dump(exclude_none=True)
        assert dumped == {
            "aw_program_id": 598,
            "source_kind": "link",
            "source_url": "https://example.com",
        }


# ===========================================================================
# chunk_pages overlap > 0 behavior
# ===========================================================================


class TestChunkPagesOverlap:
    """Overlap must duplicate the window tail into the next chunk AND the loop
    must terminate (start advances by max_tokens - overlap each round)."""

    def test_overlap_duplicates_window_tail(self) -> None:
        from src.ingestion.connectors.manifestos.mappers.corpus import _get_encoding

        enc = _get_encoding()
        text = " ".join(f"w{i}" for i in range(60))  # ASCII → no FFFD stripping
        all_tokens = enc.encode(text)
        max_tokens, overlap = 20, 5

        chunks = chunk_pages([(1, text)], max_tokens=max_tokens, overlap=overlap)

        assert len(chunks) > 1
        # Chunk k spans tokens [k*(max-o), k*(max-o)+max) — pin the exact spans.
        step = max_tokens - overlap
        for k, (chunk_text, _ps, _pe) in enumerate(chunks):
            start = k * step
            end = min(start + max_tokens, len(all_tokens))
            assert chunk_text == enc.decode(all_tokens[start:end]), (
                f"chunk {k} does not match token span [{start}:{end}]"
            )
        # The overlapped region is literally duplicated across neighbours.
        for k in range(len(chunks) - 1):
            start_next = (k + 1) * step
            shared = enc.decode(all_tokens[start_next : start_next + overlap])
            assert chunks[k][0].endswith(shared)
            assert chunks[k + 1][0].startswith(shared)

    def test_overlap_terminates_and_covers_all_tokens(self) -> None:
        from src.ingestion.connectors.manifestos.mappers.corpus import _get_encoding

        enc = _get_encoding()
        text = " ".join(f"w{i}" for i in range(203))
        chunks = chunk_pages([(1, text)], max_tokens=50, overlap=10)

        # Terminates (no infinite loop) and the final chunk carries the true tail.
        all_tokens = enc.encode(text)
        assert chunks[-1][0].endswith(enc.decode(all_tokens[-5:]))
        # Every chunk respects the token budget.
        for chunk_text, _ps, _pe in chunks:
            assert len(enc.encode(chunk_text)) <= 50

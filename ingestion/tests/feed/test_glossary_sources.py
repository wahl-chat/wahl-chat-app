# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from ingestion.feed.glossary_sources import (
    GlossarySource,
    allowed_sources,
    is_allowed,
    page_text,
    passage,
    read_sources,
)

_REDIRECT = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/"


def test_only_the_official_domains_are_sources() -> None:
    assert is_allowed("https://www.bundestag.de/services/glossar/akt_stunde-245318")
    assert is_allowed("https://bpb.de/kurz-knapp/lexika/politiklexikon/1/x/")
    assert is_allowed("https://www.bundesregierung.de/breg-de/x")
    assert not is_allowed("https://de.wikipedia.org/wiki/Aktuelle_Stunde")
    # A look-alike host is not the domain.
    assert not is_allowed("https://bundestag.de.example.com/x")
    assert not is_allowed("https://notbundestag.de/x")
    # A speech on an official site is a voice, not an explanation.
    assert not is_allowed(
        "https://www.bundesregierung.de/breg-de/service/newsletter-und-abos/"
        "bulletin/rede-der-bundesministerin-der-verteidigung-1752848"
    )
    # An archived page may state a rule since changed.
    assert not is_allowed(
        "https://www.bundestag.de/webarchiv/textarchiv/2010/29211275_kw14_gesetzentwurf-201480"
    )


def test_search_results_resolve_and_keep_only_official_pages() -> None:
    targets = {
        f"{_REDIRECT}a": "https://www.bundestag.de/services/glossar/akt_stunde-245318",
        f"{_REDIRECT}b": "https://de.wikipedia.org/wiki/Aktuelle_Stunde",
        f"{_REDIRECT}c": "https://www.bundestag.de/services/glossar/akt_stunde-245318",
    }
    metadata = {
        "grounding_metadata": {
            "grounding_chunks": [
                {"web": {"uri": uri, "title": "bundestag.de"}} for uri in targets
            ]
        }
    }
    assert allowed_sources(metadata, resolve=targets.__getitem__) == [
        GlossarySource(
            url="https://www.bundestag.de/services/glossar/akt_stunde-245318",
            title="bundestag.de",
        )
    ]
    assert allowed_sources({}, resolve=targets.__getitem__) == []


def test_a_page_is_read_without_its_scripts_and_chrome() -> None:
    title, text = page_text(
        "<html><head><title> Aktuelle Stunde -\n Deutscher Bundestag</title>"
        "<script>var x = 1;</script></head><body><nav>Menü</nav>"
        "<p>In einer Aktuellen Stunde</p><footer>Impressum</footer></body></html>"
    )
    assert title == "Aktuelle Stunde - Deutscher Bundestag"
    assert text == "In einer Aktuellen Stunde"


def test_a_short_page_is_read_whole() -> None:
    assert passage("Kurz.", ["Obmann"], limit=100) == "Kurz."


def test_a_long_page_gives_every_mention_of_the_term_and_its_forms() -> None:
    filler = "x " * 2000
    text = (
        f"Obleute sind Ansprechpartner. {filler}"
        f"Nichts dazu. {filler}"
        f"Der Obmann stimmt die Tagesordnung ab. {filler}"
    )
    found = passage(text, ["Obmann", "Obleute"], limit=3000)
    assert "Obleute sind Ansprechpartner" in found
    assert "Der Obmann stimmt die Tagesordnung ab" in found
    assert "Nichts dazu" not in found
    assert len(found) <= 3000 + 10


def test_an_unreadable_source_is_skipped_and_a_read_one_titled_by_its_page() -> None:
    def fetch(url: str) -> str:
        if "broken" in url:
            raise OSError("down")
        return "<title>Obleute - Deutscher Bundestag</title><p>Obleute sind …</p>"

    read = read_sources(
        [
            GlossarySource(url="https://www.bundestag.de/broken", title="x"),
            GlossarySource(url="https://www.bundestag.de/obleute", title="x"),
        ],
        ["Obmann", "Obleute"],
        fetch,
    )
    assert [(p.source.title, p.text) for p in read] == [
        ("Obleute - Deutscher Bundestag", "Obleute sind …")
    ]

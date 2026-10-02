# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import date
from pathlib import Path

from src.daily_digest.protocol_pages import (
    attach_protocol_pages,
    page_index,
    protocol_xml_url,
)
from src.daily_digest.reader import assemble_speeches, group_sitting_days

_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "ingestion"
    / "connectors"
    / "bundestag_speeches"
    / "fixtures"
    / "protocol_sample.xml"
)
_PDF = "https://dserver.bundestag.de/btp/21/21089.pdf"


def _sitting(speech_key: str, *, source: str = "op", pdf: str | None = _PDF):
    payload = {
        "source_item_id": "s1",
        "source": source,
        "speech_key": speech_key,
        "text": "Rede",
        "chunk_index": 0,
        "publish_date": "2026-07-09",
        "party_id": "spd",
        "citation_url": "https://video/1.mp4#t=1",
        "citation_title": "Olaf Scholz",
        "content_hash": "h",
        "meta": {"speaker_name": "Olaf Scholz", "transcript_pdf_url": pdf},
    }
    sitting = group_sitting_days(assemble_speeches([payload]))[date(2026, 7, 9)]
    sitting.protocols = [("21/89", pdf)]
    return sitting


def test_protocol_xml_url_only_rewrites_bundestag_protocol_pdfs() -> None:
    assert protocol_xml_url(_PDF + "#page=3") == (
        "https://dserver.bundestag.de/btp/21/21089.xml"
    )
    assert protocol_xml_url("https://example.org/21089.pdf") is None


def test_page_index_keys_speeches_like_the_corpus() -> None:
    pages = page_index(_FIXTURE.read_text(encoding="utf-8"), ep=21, session=89)
    assert pages["de-21-89-olaf-scholz-"] == 2


def test_attach_links_speeches_to_their_protocol_page() -> None:
    sitting = _sitting("de-21-89-olaf-scholz-")
    attached = attach_protocol_pages(
        sitting, fetch=lambda _url: _FIXTURE.read_text(encoding="utf-8")
    )
    speech = sitting.agenda_items[0].speeches[0]
    assert attached == 1
    assert speech.protocol_page_url == f"{_PDF}#page=2"


def test_attach_survives_an_unreachable_protocol() -> None:
    sitting = _sitting("de-21-89-olaf-scholz-")

    def fail(_url: str) -> str:
        raise OSError("offline")

    assert attach_protocol_pages(sitting, fetch=fail) == 0
    assert sitting.agenda_items[0].speeches[0].protocol_page_url is None


def test_dip_speeches_keep_their_own_page_anchor() -> None:
    payload = {
        "source_item_id": "d1",
        "source": "dip",
        "speech_key": "de-21-89-anna-top1",
        "text": "Rede",
        "chunk_index": 0,
        "publish_date": "2026-07-09",
        "party_id": "spd",
        "citation_url": f"{_PDF}#page=7",
        "content_hash": "h",
        "meta": {"speaker_name": "Anna", "protocol_id": "21/89"},
    }
    [speech] = assemble_speeches([payload])
    assert speech.protocol_page_url == f"{_PDF}#page=7"

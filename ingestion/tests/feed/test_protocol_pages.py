# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import date
from pathlib import Path

from ingestion.feed.protocol_pages import (
    apply_protocols,
    protocol_index,
    protocol_xml_url,
)
from ingestion.feed.reader import SittingDay, assemble_speeches, group_sitting_days

_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "connectors"
    / "bundestag_speeches"
    / "fixtures"
    / "protocol_sample.xml"
)
_PDF = "https://dserver.bundestag.de/btp/21/21089.pdf"


def _rede(rede_id: str, first: str, last: str, fraktion: str) -> str:
    return f"""
      <rede id="{rede_id}">
        <p klasse="redner"><redner id="{rede_id}0"><name>
          <vorname>{first}</vorname><nachname>{last}</nachname>
          <fraktion>{fraktion}</fraktion>
        </name></redner>{first} {last} ({fraktion}):</p>
        <p klasse="J">Rede von {last}.</p>
      </rede>"""


# Four speeches under TOP 20 (Clara twice), then a Befragung in which Anna
# and Bernd ask several questions.
_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<dbtplenarprotokoll sitzung-datum="09.07.2026" start-seitennr="1">
  <vorspann>
    <inhaltsverzeichnis>
      <xref ref-type="rede" rid="ID1" pnr="3" div="A"/>
      <xref ref-type="rede" rid="ID2" pnr="5" div="B"/>
      <xref ref-type="rede" rid="ID3" pnr="6" div="A"/>
      <xref ref-type="rede" rid="ID4" pnr="8" div="C"/>
    </inhaltsverzeichnis>
  </vorspann>
  <sitzungsverlauf>
    <tagesordnungspunkt top-id="Tagesordnungspunkt 20">
      {_rede("ID1", "Clara", "Weiss", "SPD")}
      {_rede("ID2", "Anna", "Berg", "CDU/CSU")}
      {_rede("ID3", "Bernd", "Roth", "AfD")}
      {_rede("ID4", "Clara", "Weiss", "SPD")}
    </tagesordnungspunkt>
    <tagesordnungspunkt top-id="Tagesordnungspunkt 1">
      {_rede("ID5", "Anna", "Berg", "CDU/CSU")}
      {_rede("ID6", "Bernd", "Roth", "AfD")}
      {_rede("ID7", "Anna", "Berg", "CDU/CSU")}
      {_rede("ID8", "Bernd", "Roth", "AfD")}
    </tagesordnungspunkt>
  </sitzungsverlauf>
</dbtplenarprotokoll>"""


def _payload(
    sid: str, key: str, speaker: str, source: str = "op", day: str = "2026-07-09"
) -> dict:
    return {
        "source_item_id": sid,
        "source": source,
        "speech_key": key,
        "text": "Rede",
        "chunk_index": 0,
        "publish_date": day,
        "party_id": "spd",
        "citation_url": f"https://video/{sid}.mp4#t=1",
        "citation_title": speaker,
        "content_hash": sid,
        "meta": {"speaker_name": speaker, "transcript_pdf_url": _PDF},
    }


def _sitting(payloads: list[dict]) -> SittingDay:
    sitting = group_sitting_days(assemble_speeches(payloads))[date(2026, 7, 9)]
    sitting.protocols = [("21/89", _PDF)]
    return sitting


def _top20_sitting() -> SittingDay:
    # Fed in an order that is not the protocol's.
    return _sitting(
        [
            _payload("a", "de-21-89-bernd-roth-top20", "Bernd Roth"),
            _payload("b", "de-21-89-clara-weiss-top20", "Clara Weiss"),
            _payload("c", "de-21-89-anna-berg-top20", "Anna Berg"),
            _payload("d", "de-21-89-clara-weiss-top20", "Clara Weiss"),
            _payload("e", "de-21-89-nobody-top20", "Nobody"),
        ]
    )


def test_protocol_xml_url_only_rewrites_bundestag_protocol_pdfs() -> None:
    assert protocol_xml_url(_PDF + "#page=3") == (
        "https://dserver.bundestag.de/btp/21/21089.xml"
    )
    assert protocol_xml_url("https://example.org/21089.pdf") is None


def test_the_index_slugs_speakers_and_agenda_items_like_the_corpus() -> None:
    index = protocol_index(_FIXTURE.read_text(encoding="utf-8"))
    first = index.speeches[0]
    assert (first.position, first.page, first.speaker, first.agenda) == (
        0,
        2,
        "olaf-scholz",
        "",
    )


def test_the_index_keeps_every_speech_in_order_and_the_session_date() -> None:
    index = protocol_index(_XML)
    assert index.session_date == date(2026, 7, 9)
    assert [(p.speaker, p.agenda) for p in index.speeches[:4]] == [
        ("clara-weiss", "top20"),
        ("anna-berg", "top20"),
        ("bernd-roth", "top20"),
        ("clara-weiss", "top20"),
    ]
    assert [p.page for p in index.speeches[:4]] == [3, 5, 6, 8]


def test_speeches_are_put_in_protocol_order_and_linked_to_their_page() -> None:
    sitting = _top20_sitting()
    assert apply_protocols(sitting, fetch=lambda _url: _XML) == 1
    [item] = sitting.agenda_items
    assert item.ordered
    # The speaker who spoke twice takes both of her places; a speech the
    # protocol does not list goes last.
    assert [s.source_item_id for s in item.speeches] == ["b", "c", "a", "d", "e"]
    assert [s.protocol_page_url for s in item.speeches] == [
        f"{_PDF}#page=3",
        f"{_PDF}#page=5",
        f"{_PDF}#page=6",
        f"{_PDF}#page=8",
        None,
    ]


def test_an_unreachable_protocol_leaves_the_debate_unordered() -> None:
    sitting = _top20_sitting()

    def fail(_url: str) -> str:
        raise OSError("offline")

    assert apply_protocols(sitting, fetch=fail) == 0
    assert not sitting.agenda_items[0].ordered
    assert sitting.agenda_items[0].speeches[0].protocol_page_url is None


def test_a_protocol_without_speeches_yet_orders_nothing() -> None:
    sitting = _top20_sitting()
    empty = '<?xml version="1.0"?><dbtplenarprotokoll sitzung-datum="09.07.2026"/>'
    assert apply_protocols(sitting, fetch=lambda _url: empty) == 0
    assert not sitting.agenda_items[0].ordered


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


def test_a_debate_filed_under_another_item_is_found_by_its_speakers() -> None:
    # openparliament.tv files the joint debate under ZP 19; the protocol keeps
    # it under TOP 20. Anna and Bernd also asked questions in TOP 1, more often
    # than they spoke in TOP 20, but fewer of the debate's speakers did.
    sitting = _sitting(
        [
            _payload("b", "de-21-89-bernd-roth-zp19", "Bernd Roth"),
            _payload("c", "de-21-89-clara-weiss-zp19", "Clara Weiss"),
            _payload("a", "de-21-89-anna-berg-zp19", "Anna Berg"),
        ]
    )
    apply_protocols(sitting, fetch=lambda _url: _XML)
    [item] = sitting.agenda_items
    assert [s.source_item_id for s in item.speeches] == ["c", "a", "b"]
    assert item.speeches[1].protocol_page_url == f"{_PDF}#page=5"


def test_a_speech_held_by_both_sources_is_kept_once_from_op() -> None:
    sitting = _sitting(
        [
            _payload("op-a", "de-21-89-anna-berg-zp19", "Anna Berg"),
            _payload("op-c", "de-21-89-clara-weiss-zp19", "Clara Weiss"),
            _payload("dip-a", "de-21-89-anna-berg-top20", "Anna Berg", source="dip"),
            _payload(
                "dip-c", "de-21-89-clara-weiss-top20", "Clara Weiss", source="dip"
            ),
        ]
    )
    apply_protocols(sitting, fetch=lambda _url: _XML)
    assert [i.key for i in sitting.agenda_items] == ["89:zp19"]
    assert [s.source_item_id for s in sitting.agenda_items[0].speeches] == [
        "op-c",
        "op-a",
    ]


def test_a_speech_whose_key_lacks_the_speaker_is_matched_by_name() -> None:
    sitting = _sitting(
        [
            _payload("x", "de-21-89--top20", "Bernd Roth"),
            _payload("y", "de-21-89-clara-weiss-top20", "Clara Weiss"),
        ]
    )
    apply_protocols(sitting, fetch=lambda _url: _XML)
    assert [s.source_item_id for s in sitting.agenda_items[0].speeches] == ["y", "x"]


def test_an_item_the_protocol_does_not_list_is_left_out() -> None:
    sitting = _sitting(
        [
            _payload("a", "de-21-89-anna-berg-top20", "Anna Berg"),
            _payload("x", "de-21-89-xaver-unbekannt-top3", "Xaver Unbekannt"),
        ]
    )
    assert apply_protocols(sitting, fetch=lambda _url: _XML) == 1
    assert [i.key for i in sitting.agenda_items] == ["89:top20"]

# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import date
from types import SimpleNamespace

import pytest

from src.daily_digest.reader import (
    assemble_speeches,
    compute_window,
    group_sitting_days,
    latest_publish_date,
    parse_speech_key,
    window_filter,
)


def _speech_chunk(
    *,
    sid: str,
    source: str,
    key: str,
    text: str,
    chunk_index: int = 0,
    day: str = "2026-09-24",
    meta: dict | None = None,
    citation_url: str | None = None,
) -> dict:
    return {
        "source_item_id": sid,
        "source": source,
        "speech_key": key,
        "text": text,
        "chunk_index": chunk_index,
        "publish_date": day,
        "party_id": "spd",
        "citation_url": citation_url,
        "citation_title": f"{sid} title",
        "content_hash": f"h-{sid}-{chunk_index}",
        "meta": meta or {},
    }


def test_parse_speech_key_extracts_session_and_agenda() -> None:
    assert parse_speech_key("de-21-45-mareike-lotte-wulf-top20") == ((21, 45), "top20")
    assert parse_speech_key("de-21-45-anna-zp3") == ((21, 45), "zp3")


def test_parse_speech_key_tolerates_missing_agenda_and_garbage() -> None:
    assert parse_speech_key("de-21-45-anna-") == ((21, 45), "")
    assert parse_speech_key(None) == (None, "")
    assert parse_speech_key("nonsense") == (None, "")


def test_assemble_speeches_rejoins_chunks_in_order() -> None:
    payloads = [
        _speech_chunk(
            sid="a",
            source="dip",
            key="de-21-45-anna-top1",
            text="second",
            chunk_index=1,
        ),
        _speech_chunk(
            sid="a", source="dip", key="de-21-45-anna-top1", text="first", chunk_index=0
        ),
    ]
    [speech] = assemble_speeches(payloads)
    assert speech.text == "first second"
    assert speech.content_hashes == ["h-a-0", "h-a-1"]


def test_assemble_speeches_prefers_op_over_its_dip_twin() -> None:
    key = "de-21-45-anna-top1"
    payloads = [
        _speech_chunk(sid="dip-1", source="dip", key=key, text="dip text"),
        _speech_chunk(
            sid="op-1",
            source="op",
            key=key,
            text="op text",
            meta={"video_uri": "https://video/1.mp4", "agenda_item_title": "Haushalt"},
        ),
    ]
    speeches = assemble_speeches(payloads)
    assert [s.source_item_id for s in speeches] == ["op-1"]
    assert speeches[0].video_uri == "https://video/1.mp4"


def test_group_sitting_days_orders_agenda_items_and_labels_them() -> None:
    payloads = [
        _speech_chunk(sid="s2", source="dip", key="de-21-45-anna-top12", text="b"),
        _speech_chunk(
            sid="s1",
            source="op",
            key="de-21-45-ben-top3",
            text="a",
            meta={"agenda_item_title": "Rente"},
        ),
        _speech_chunk(sid="s3", source="dip", key="de-21-45-cara-", text="c"),
    ]
    days = group_sitting_days(assemble_speeches(payloads))
    sitting = days[date(2026, 9, 24)]
    assert [item.label for item in sitting.agenda_items] == [
        "Rente",
        "Tagesordnungspunkt 12",
        "Sonstige Wortbeiträge",
    ]


def test_group_sitting_days_takes_the_dip_protocol_pdf_without_page_anchor() -> None:
    payloads = [
        _speech_chunk(
            sid="s1",
            source="dip",
            key="de-21-45-anna-top1",
            text="a",
            meta={"protocol_id": "21/45"},
            citation_url="https://dserver.bundestag.de/btp/21/21045.pdf#page=12",
        )
    ]
    sitting = group_sitting_days(assemble_speeches(payloads))[date(2026, 9, 24)]
    assert sitting.protocols == [
        ("21/45", "https://dserver.bundestag.de/btp/21/21045.pdf")
    ]


def test_compute_window_ends_on_latest_day() -> None:
    assert compute_window(date(2026, 9, 26), 14) == (
        date(2026, 9, 13),
        date(2026, 9, 26),
    )
    with pytest.raises(ValueError):
        compute_window(date(2026, 9, 26), 0)


def test_window_filter_is_end_inclusive() -> None:
    flt = window_filter("vote_record", "DE-BW", date(2026, 9, 1), date(2026, 9, 14))
    date_range = flt.must[2].range  # type: ignore[index, union-attr]
    assert date_range.gte.date() == date(2026, 9, 1)
    assert date_range.lt.date() == date(2026, 9, 15)


def test_latest_publish_date_takes_the_max_across_source_types() -> None:
    latest_by_type = {"vote_record": "2026-09-20", "parliamentary_speech": "2026-09-25"}

    class FakeClient:
        def scroll(self, *, scroll_filter, **_kwargs):  # type: ignore[no-untyped-def]
            source_type = scroll_filter.must[0].match.value
            point = SimpleNamespace(
                payload={"publish_date": latest_by_type[source_type]}
            )
            return [point], None

    found = latest_publish_date(
        FakeClient(),  # type: ignore[arg-type]
        "c",
        ["vote_record", "parliamentary_speech"],
        "DE",
    )
    assert found == date(2026, 9, 25)

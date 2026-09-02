# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
PledgeTracker mapper unit tests (stub fixture + live merge_result + to_chunk).

Tests defined here:
  - test_stub_normalize_returns_chunk_records: normalize() → list[ChunkRecord].
  - test_stub_normalize_record_maps_fixture: fixture fields land on PledgeRecord,
    incl. Ja/Nein → is_relevant_for_tracking (NOT a fulfilment verdict).
  - test_merge_result_maps_events_and_registry_metadata: live results merge the
    registry row's descriptive fields with the pipeline's events; the event
    `content` (full source text) is never stored; `title` is kept.
  - test_merge_result_without_events_raises: missing events list = failure.
  - test_merge_result_with_empty_events_is_valid: empty list = "no evidence yet".
  - test_to_chunk_builds_pledge_envelope: the Qdrant payload carries the six
    indexed pledge fields plus source_parent_key/content_hash, keeps timelines
    out of the embedded text, and one pledge = one chunk.
  - test_to_chunk_content_hash_tracks_refreshes: a refreshed check date changes
    content_hash so re-ingestion rewrites the point.
"""

from __future__ import annotations

from src.ingestion.connectors.pledgetracker.connector import PledgeTrackerConnector
from src.ingestion.connectors.pledgetracker.registry import PledgeInput
from src.ingestion.schemas import ChunkRecord, SourceType

_README_RESULT = {
    "status": "success",
    "language": "de",
    "events": [
        {
            "date": "2026-01-05",
            "event": "Aktuelle Ausschreibungen der DEGES GmbH ...",
            "url": "https://padoka.landtag.sachsen-anhalt.de/doc.pdf",
            "title": "Ausschreibung A14",
            "content": "...full source text that must never reach Firestore...",
            "bundesland": "Sachsen-Anhalt",
            "quelle": "Landesparlament",
            "partei": "['CDU', 'SPD', 'FDP']",
            "label": "Ja",
            "confident": -0.20,
        },
        {
            "date": "2025-06-01",
            "event": "Kontext-Ereignis ohne Tracking-Relevanz.",
            "label": "Nein",
        },
    ],
    "artifacts": {"internal": "/gpu/path"},
}


def _cdu_input() -> PledgeInput:
    return PledgeInput(
        claim="Wir wollen, dass die A14 fertig wird",
        pledge_date="2021-03-27",
        pledge_author="CDU",
        bundesland="Sachsen-Anhalt",
        policy_area="Verkehr",
        pledge_source_title="Wahlprogramm CDU Sachsen-Anhalt 2021",
    )


def test_stub_normalize_returns_chunk_records() -> None:
    """normalize() must return list[ChunkRecord] (one vector per pledge)."""
    connector = PledgeTrackerConnector(stub=True)
    raw = connector.fetch("spd-mindestlohn-12-euro-de-2021")
    result = connector.normalize(raw)

    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], ChunkRecord)


def test_stub_normalize_record_maps_fixture() -> None:
    """Fixture fields land on PledgeRecord; Ja/Nein maps to tracking relevance."""
    connector = PledgeTrackerConnector(stub=True)
    raw = connector.fetch("spd-mindestlohn-12-euro-de-2021")
    record = connector.normalize_record(raw)

    assert record.pledge_id == "spd-mindestlohn-12-euro-de-2021"
    assert record.party_id == "spd"
    assert record.tracker_status == "in_progress"
    assert record.timeline_events[0].is_relevant_for_tracking is True
    assert record.timeline_events[1].is_relevant_for_tracking is False
    assert record.timeline_events[1].raw_label == "Nein"
    # Schema-ready display fields stay empty until real data provides them.
    assert record.tracker_status_label is None
    assert record.tracker_step is None


def test_merge_result_maps_events_and_registry_metadata() -> None:
    """Registry metadata + pipeline events merge; `content` is never stored."""
    connector = PledgeTrackerConnector(stub=True)
    record = connector.merge_result(_cdu_input(), _README_RESULT)

    assert record.party_id == "cdu"
    assert record.region == "DE-ST"
    assert record.region_path == ["DE", "DE-ST"]
    assert record.policy_area == "Verkehr"
    assert record.pledge_source_title == "Wahlprogramm CDU Sachsen-Anhalt 2021"
    assert record.tracker_status == "in_progress"
    assert record.last_checked_at is not None

    assert len(record.timeline_events) == 2
    event = record.timeline_events[0]
    assert event.is_relevant_for_tracking is True
    assert event.title == "Ausschreibung A14"
    assert event.source == "Landesparlament"
    # Full source text must never reach Firestore (1MB doc cap; url suffices).
    assert "content" not in event.model_dump()


def test_merge_result_without_events_raises() -> None:
    """A result without an events list is a failure, not an empty timeline."""
    connector = PledgeTrackerConnector(stub=True)
    try:
        connector.merge_result(_cdu_input(), {"status": "error"})
    except ValueError as exc:
        assert "events list" in str(exc)
    else:
        raise AssertionError("merge_result must raise without an events list")


def test_merge_result_with_empty_events_is_valid() -> None:
    """Empty events = 'no evidence yet' — still a record (freshness applies)."""
    connector = PledgeTrackerConnector(stub=True)
    record = connector.merge_result(
        _cdu_input(), {"status": "success", "events": []}
    )
    assert record.timeline_events == []


def test_to_chunk_builds_pledge_envelope() -> None:
    """The Qdrant payload carries the indexed pledge fields; no timeline text."""
    connector = PledgeTrackerConnector(stub=True)
    record = connector.merge_result(_cdu_input(), _README_RESULT)
    chunk = connector.to_chunk(record)

    assert chunk.source_type == SourceType.PLEDGE_RECORD
    assert chunk.party_id == "cdu"
    assert chunk.region == "DE-ST"
    assert chunk.pledge_id == record.pledge_id
    assert chunk.claim_id == record.pledge_id
    assert chunk.status == "in_progress"
    assert chunk.as_of_date is not None
    assert chunk.policy_area == "Verkehr"
    assert chunk.external_id is None
    assert chunk.source_parent_key == f"pledge_record:{record.pledge_id}"
    assert chunk.content_hash is not None
    assert chunk.chunk_index == 0
    # Timeline evidence stays out of the embedded text.
    assert "DEGES" not in chunk.text
    assert "Versprechen" in chunk.text


def test_to_chunk_content_hash_tracks_refreshes() -> None:
    """A refreshed check date changes content_hash → the point gets rewritten."""
    connector = PledgeTrackerConnector(stub=True)
    record = connector.merge_result(_cdu_input(), _README_RESULT)
    first = connector.to_chunk(record)
    refreshed = record.model_copy(update={"last_checked_at": "2030-01-01T00:00:00+00:00"})
    second = connector.to_chunk(refreshed)
    assert first.content_hash != second.content_hash

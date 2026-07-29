# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Tests for the AW-wins supersede of an uploaded manifesto.

The delete is destructive and driven by a three-field identity, so the tests pin
both directions: it fires on an exact party+region+election-date agreement, and it
does NOT fire on any disagreement — the safe failure mode is a visible duplicate,
never a wrongly removed document.
"""

from __future__ import annotations

import uuid
from datetime import date

from src.ingestion.connectors.manifestos.supersede import (
    supersede_uploaded_manifestos,
)
from src.ingestion.schemas import AuthorityTier, ChunkRecord, SourceType


def _aw_chunk(
    *,
    party_id: str = "spd",
    region: str = "DE-ST",
    publish_date: date = date(2026, 9, 6),
    chunk_index: int = 0,
) -> ChunkRecord:
    sid = uuid.uuid5(uuid.NAMESPACE_DNS, f"{party_id}:{region}:{publish_date}")
    return ChunkRecord(
        chunk_key=f"{sid}:{chunk_index:04d}",
        source_item_id=sid,
        chunk_index=chunk_index,
        text="Aus dem Wahlprogramm.",
        party_id=party_id,
        region=region,
        authority_tier=AuthorityTier.SELF_REPORTED,
        source_type=SourceType.PARTY_MANIFESTO,
        publish_date=publish_date,
        external_id=4711,
    )


class _FakeQdrant:
    """Counts matching uploaded chunks and records deletes."""

    def __init__(self, matches: int) -> None:
        self._matches = matches
        self.count_filters: list[object] = []
        self.deletes: list[object] = []

    def count(self, **kwargs):  # noqa: ANN003, ANN201
        self.count_filters.append(kwargs.get("count_filter"))
        return type("R", (), {"count": self._matches})()

    def delete(self, **kwargs):  # noqa: ANN003, ANN201
        self.deletes.append(kwargs.get("points_selector"))


def _conditions(flt) -> dict:  # noqa: ANN001
    out = {}
    for cond in getattr(flt, "must", []) or []:
        if getattr(cond, "match", None) is not None:
            out[cond.key] = cond.match.value
        elif getattr(cond, "range", None) is not None:
            out[cond.key] = cond.range
    return out


def test_deletes_the_uploaded_twin_when_one_exists() -> None:
    qdrant = _FakeQdrant(matches=214)
    assert supersede_uploaded_manifestos(qdrant, "c", [_aw_chunk()]) == 1
    assert len(qdrant.deletes) == 1


def test_no_delete_when_nothing_matches() -> None:
    qdrant = _FakeQdrant(matches=0)
    assert supersede_uploaded_manifestos(qdrant, "c", [_aw_chunk()]) == 0
    assert qdrant.deletes == []


def test_filter_targets_only_uploaded_manifestos_of_that_party_and_region() -> None:
    qdrant = _FakeQdrant(matches=1)
    supersede_uploaded_manifestos(qdrant, "c", [_aw_chunk()])
    conditions = _conditions(qdrant.count_filters[0])
    assert conditions["source_type"] == "party_manifesto"
    # Never deletes another AW programme — only the upload half.
    assert conditions["source"] == "upload"
    assert conditions["party_id"] == "spd"
    assert conditions["region"] == "DE-ST"
    # The election date is matched as a single closed day, not an open range.
    window = conditions["publish_date"]
    assert window.gte.date() == window.lte.date() == date(2026, 9, 6)


def test_one_delete_per_party_region_date_group() -> None:
    qdrant = _FakeQdrant(matches=1)
    chunks = [
        _aw_chunk(chunk_index=0),
        _aw_chunk(chunk_index=1),
        _aw_chunk(chunk_index=2),
    ]
    # All chunks of one programme share the identity — one delete, not three.
    assert supersede_uploaded_manifestos(qdrant, "c", chunks) == 1
    assert len(qdrant.deletes) == 1


def test_distinct_parties_are_superseded_independently() -> None:
    qdrant = _FakeQdrant(matches=1)
    chunks = [_aw_chunk(party_id="spd"), _aw_chunk(party_id="cdu")]
    assert supersede_uploaded_manifestos(qdrant, "c", chunks) == 2
    parties = {_conditions(f)["party_id"] for f in qdrant.count_filters}
    assert parties == {"spd", "cdu"}


def test_a_different_region_is_not_superseded() -> None:
    # A federal AW programme must never delete a state-election upload.
    qdrant = _FakeQdrant(matches=1)
    supersede_uploaded_manifestos(qdrant, "c", [_aw_chunk(region="DE")])
    assert _conditions(qdrant.count_filters[0])["region"] == "DE"


def test_a_different_election_date_is_not_superseded() -> None:
    # Dates disagreeing means the two records are not the same election, so the
    # filter simply matches nothing — a duplicate is preferable to a wrong delete.
    qdrant = _FakeQdrant(matches=1)
    supersede_uploaded_manifestos(
        qdrant, "c", [_aw_chunk(publish_date=date(2021, 6, 6))]
    )
    assert _conditions(qdrant.count_filters[0])["publish_date"].gte.date() == date(
        2021, 6, 6
    )


def test_non_manifesto_chunks_are_ignored() -> None:
    qdrant = _FakeQdrant(matches=1)
    assert supersede_uploaded_manifestos(qdrant, "c", []) == 0
    assert qdrant.count_filters == []

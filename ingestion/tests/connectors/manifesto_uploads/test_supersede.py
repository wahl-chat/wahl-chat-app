# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Tests for the AW-wins supersede of an uploaded Wahlprogramm.

This is the common overlap direction — a party sends us a draft, AW publishes the
final text later — so it fires immediately from AW's post_upsert rather than waiting
for the next uploads run. It is destructive, so the tests pin the blast radius:

  * a Wahlprogramm IS retired on an exact party+region+election-date agreement;
  * a Grundsatzprogramm or Satzung under the SAME triple is NOT — AW publishes no
    such document, and deleting it was the bug this class folder exists to prevent;
  * the delete is addressed by the documents' own source_item_ids, never by the
    party+region+date filter used to find them.
"""

from __future__ import annotations

import logging
import types
import uuid
from datetime import date

import pytest

from ingestion.connectors.manifesto_uploads.mappers.corpus import UPLOAD_SOURCE
from ingestion.connectors.manifestos.supersede import (
    supersede_uploaded_wahlprogramme,
)
from ingestion.ids import compute_source_item_id
from ingestion.schemas import AuthorityTier, ChunkRecord, SourceType

_CTX = "landtagswahl-sachsen-anhalt-2026"
_WP = f"public/{_CTX}/wahlprogramme/spd/Wahlprogramm-SPD_2026-06-01.pdf"
_WP2 = f"public/{_CTX}/wahlprogramme/spd/Wahlprogramm-SPD-Teil-2_2026-06-01.pdf"
_SATZUNG = f"public/{_CTX}/parteidokumente/spd/Satzung-SPD_2019-11-30.pdf"


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


def _sid_of(object_path: str) -> str:
    return str(
        compute_source_item_id(
            SourceType.PARTY_MANIFESTO.value, object_path, source=UPLOAD_SOURCE
        )
    )


class _FakeQdrant:
    """Serves the uploaded-twin scroll and records delete selectors."""

    def __init__(self, object_paths: tuple[str, ...] = ()) -> None:
        self._object_paths = object_paths
        self.scroll_filters: list[object] = []
        self.deletes: list[object] = []

    def scroll(self, **kwargs):  # noqa: ANN003, ANN201
        self.scroll_filters.append(kwargs.get("scroll_filter"))
        points = [
            types.SimpleNamespace(
                id=f"{path}:0", payload={"meta": {"storage_object_path": path}}
            )
            for path in self._object_paths
        ]
        return (points, None)

    def delete(self, **kwargs):  # noqa: ANN003, ANN201
        self.deletes.append(kwargs.get("points_selector"))

    # -- assertion helpers ---------------------------------------------------

    def deleted_sids(self) -> set[str]:
        found: set[str] = set()
        for selector in self.deletes:
            for cond in getattr(getattr(selector, "filter", None), "must", []) or []:
                if cond.key == "source_item_id":
                    found.update(getattr(cond.match, "any", []) or [])
        return found


def _conditions(flt) -> dict:  # noqa: ANN001
    out = {}
    for cond in getattr(flt, "must", []) or []:
        if getattr(cond, "match", None) is not None:
            out[cond.key] = cond.match.value
        elif getattr(cond, "range", None) is not None:
            out[cond.key] = cond.range
    return out


# ===========================================================================
# What is retired
# ===========================================================================


def test_retires_the_uploaded_wahlprogramm(caplog: pytest.LogCaptureFixture) -> None:
    qdrant = _FakeQdrant(object_paths=(_WP,))
    with caplog.at_level(logging.WARNING):
        assert supersede_uploaded_wahlprogramme(qdrant, "c", [_aw_chunk()]) == 1
    assert qdrant.deleted_sids() == {_sid_of(_WP)}
    assert _WP in caplog.text


def test_a_parteidokument_under_the_same_triple_is_kept() -> None:
    """The regression the class folder exists for.

    A Satzung carries the election's publish_date and region like everything else, so
    the discovery filter finds it — but AW publishes no Satzung, and the old
    filter-driven delete removed it anyway.
    """
    qdrant = _FakeQdrant(object_paths=(_SATZUNG,))
    assert supersede_uploaded_wahlprogramme(qdrant, "c", [_aw_chunk()]) == 0
    assert qdrant.deletes == [], "an AW programme must not delete a Satzung"


def test_mixed_classes_retire_only_the_wahlprogramm() -> None:
    qdrant = _FakeQdrant(object_paths=(_WP, _SATZUNG))
    assert supersede_uploaded_wahlprogramme(qdrant, "c", [_aw_chunk()]) == 1
    assert qdrant.deleted_sids() == {_sid_of(_WP)}
    assert _sid_of(_SATZUNG) not in qdrant.deleted_sids()


def test_a_split_programme_is_retired_as_a_whole() -> None:
    """Both halves are the same programme, and the AW copy replaces that programme."""
    qdrant = _FakeQdrant(object_paths=(_WP, _WP2))
    assert supersede_uploaded_wahlprogramme(qdrant, "c", [_aw_chunk()]) == 2
    assert qdrant.deleted_sids() == {_sid_of(_WP), _sid_of(_WP2)}


def test_an_unparseable_stored_path_is_never_deleted() -> None:
    # No class can be inferred, so the safe reading is "not a Wahlprogramm".
    qdrant = _FakeQdrant(object_paths=("public/legacy/spd/whatever.pdf",))
    assert supersede_uploaded_wahlprogramme(qdrant, "c", [_aw_chunk()]) == 0
    assert qdrant.deletes == []


def test_no_upload_stored_means_no_delete() -> None:
    qdrant = _FakeQdrant(object_paths=())
    assert supersede_uploaded_wahlprogramme(qdrant, "c", [_aw_chunk()]) == 0
    assert qdrant.deletes == []


def test_non_manifesto_chunks_are_ignored() -> None:
    qdrant = _FakeQdrant(object_paths=(_WP,))
    assert supersede_uploaded_wahlprogramme(qdrant, "c", []) == 0
    assert qdrant.scroll_filters == []


# ===========================================================================
# How it is addressed
# ===========================================================================


def test_discovery_filter_targets_only_this_party_election_and_uploads() -> None:
    qdrant = _FakeQdrant(object_paths=(_WP,))
    supersede_uploaded_wahlprogramme(qdrant, "c", [_aw_chunk()])
    conditions = _conditions(qdrant.scroll_filters[0])
    assert conditions["source_type"] == "party_manifesto"
    # Never looks at another AW programme — only the upload half.
    assert conditions["source"] == "upload"
    assert conditions["party_id"] == "spd"
    assert conditions["region"] == "DE-ST"
    # The election date is matched as a single closed day, not an open range.
    window = conditions["publish_date"]
    assert window.gte.date() == window.lte.date() == date(2026, 9, 6)


def test_delete_is_addressed_by_source_item_id_not_by_the_discovery_filter() -> None:
    """The blast radius must be the documents named, not everything the filter found."""
    qdrant = _FakeQdrant(object_paths=(_WP, _SATZUNG))
    supersede_uploaded_wahlprogramme(qdrant, "c", [_aw_chunk()])
    keys = {
        cond.key
        for selector in qdrant.deletes
        for cond in getattr(getattr(selector, "filter", None), "must", []) or []
    }
    assert keys == {"source_item_id", "source"}
    assert "publish_date" not in keys and "party_id" not in keys


def test_distinct_parties_are_superseded_independently() -> None:
    qdrant = _FakeQdrant(object_paths=(_WP,))
    chunks = [_aw_chunk(party_id="spd"), _aw_chunk(party_id="cdu")]
    supersede_uploaded_wahlprogramme(qdrant, "c", chunks)
    parties = {_conditions(f)["party_id"] for f in qdrant.scroll_filters}
    assert parties == {"spd", "cdu"}


@pytest.mark.parametrize(
    ("field", "value"),
    [("region", "DE"), ("publish_date", date(2021, 6, 6))],
)
def test_identity_is_echoed_exactly_so_a_different_election_never_matches(
    field: str, value: object
) -> None:
    """A federal programme or an earlier election must not select this upload."""
    qdrant = _FakeQdrant(object_paths=(_WP,))
    supersede_uploaded_wahlprogramme(qdrant, "c", [_aw_chunk(**{field: value})])  # type: ignore[arg-type]
    conditions = _conditions(qdrant.scroll_filters[0])
    if field == "region":
        assert conditions["region"] == value
    else:
        assert conditions["publish_date"].gte.date() == value


def test_one_scroll_per_party_region_date_group() -> None:
    qdrant = _FakeQdrant(object_paths=(_WP,))
    chunks = [_aw_chunk(chunk_index=i) for i in range(3)]
    # All chunks of one programme share the identity — one pass, not three.
    supersede_uploaded_wahlprogramme(qdrant, "c", chunks)
    assert len(qdrant.scroll_filters) == 1

# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Tests for the post-ingest reachability check.

A document can be written, counted and footprint-scanned successfully and still be
absent from vector search: the collection disables the global HNSW graph (``m=0``,
tenant sub-indexes on ``party_id``), so a gap in one tenant's sub-index removes its
chunks from retrieval with no error anywhere. That really happened to the uploaded
CDU Wahlprogramm — 277 stored chunks, ``count`` fine, approximate search empty, chat
answering from a 2021 Abgeordnetenwatch copy instead.

Every other integrity check in the pipeline is count-based and structurally cannot
see this, which is why the probe is a real ANN query using the document's own stored
vector: a point that cannot retrieve itself is not reachable.

Two properties the probe must hold, both learned from real false results:

* It queries with the filter shape **chat actually uses** (``source_type`` +
  ``party_id`` + ``region``). A probe on ``party_id`` + ``source`` — a combination no
  query issues — reported every ``gruene`` upload as unreachable while chat retrieved
  them fine, because that narrow slice's filtered subgraph was unreachable while the
  real one was not.
* It asserts the probe point retrieves **itself**, by id. The production filter also
  matches the party's Abgeordnetenwatch copies, so "something came back" would let an
  unreachable upload pass on the strength of a reachable twin — exactly the regression
  this check exists to catch.
"""

from __future__ import annotations

import types

from ingestion.connectors.manifesto_uploads.bulk import verify_reachable

_CTX = "landtagswahl-sachsen-anhalt-2026"
_SPD = f"public/{_CTX}/wahlprogramme/spd/Wahlprogramm-SPD_2026-06-01.pdf"
_CDU = f"public/{_CTX}/wahlprogramme/cdu/Regierungsprogramm-CDU_2026-03-24.pdf"
_REGION = "DE-ST"


def _point_id(path: str) -> str:
    return f"{path}:0"


class _Qdrant:
    """Store whose ANN search reaches only the parties in *reachable*.

    Models the real failure exactly: scroll/count see every point (they read payload),
    while query_points cannot reach a party whose tenant sub-index is missing.
    """

    def __init__(self, stored: dict[str, str], reachable: set[str]) -> None:
        self._stored = stored  # object_path -> party_id
        self._reachable = reachable
        self.searched: list[str] = []
        self.filters: list[dict[str, str]] = []

    def scroll(self, **kwargs):  # noqa: ANN003, ANN201
        points = [
            types.SimpleNamespace(
                id=_point_id(path),
                payload={
                    "meta": {"storage_object_path": path},
                    "party_id": party,
                    "region": _REGION,
                },
                vector={"dense": [0.1] * 8},
            )
            for path, party in self._stored.items()
        ]
        return (points, None)

    def _hits_for(self, party: str) -> list[types.SimpleNamespace]:
        """The party's own chunks, when its tenant sub-index can be traversed."""
        return [
            types.SimpleNamespace(id=_point_id(path), score=1.0, payload={})
            for path, stored_party in self._stored.items()
            if stored_party == party
        ]

    def query_points(self, **kwargs):  # noqa: ANN003, ANN201
        conditions = {
            c.key: c.match.value
            for c in getattr(kwargs.get("query_filter"), "must", []) or []
            if getattr(c, "match", None) is not None
        }
        self.filters.append(conditions)
        party = conditions.get("party_id")
        self.searched.append(party)
        hits = self._hits_for(party) if party in self._reachable else []
        return types.SimpleNamespace(points=hits)


def test_a_reachable_document_is_not_flagged() -> None:
    qdrant = _Qdrant({_SPD: "spd"}, reachable={"spd"})
    assert verify_reachable(qdrant, "c") == []


def test_a_stored_but_unreachable_document_is_flagged() -> None:
    """The CDU regression: stored and counted, but invisible to search."""
    qdrant = _Qdrant({_CDU: "cdu"}, reachable=set())
    assert verify_reachable(qdrant, "c") == [_CDU]


def test_only_the_unreachable_document_is_flagged() -> None:
    qdrant = _Qdrant({_SPD: "spd", _CDU: "cdu"}, reachable={"spd"})
    assert verify_reachable(qdrant, "c") == [_CDU]


def test_the_probe_uses_the_production_filter_shape() -> None:
    """source_type + party_id + region — what _retrieve_party_buckets queries with.

    Probing a shape no query uses tells us nothing about whether chat can reach the
    document, and can be unsearchable on its own account (the gruene false alarm).
    """
    qdrant = _Qdrant({_SPD: "spd", _CDU: "cdu"}, reachable={"spd", "cdu"})
    verify_reachable(qdrant, "c")
    assert sorted(qdrant.searched) == ["cdu", "spd"]
    for conditions in qdrant.filters:
        assert set(conditions) == {"source_type", "party_id", "region"}
        assert conditions["source_type"] == "party_manifesto"
        assert conditions["region"] == _REGION


def test_a_reachable_twin_does_not_mask_an_unreachable_document() -> None:
    """The production filter also matches the party's AW copies, so a hit that is not
    the probe point itself must not count as reachable."""

    class _TwinOnly(_Qdrant):
        def _hits_for(self, party: str) -> list[types.SimpleNamespace]:
            # A different chunk of the same party+region answers, but not the probe.
            return [types.SimpleNamespace(id="aw-twin", score=0.9, payload={})]

    qdrant = _TwinOnly({_CDU: "cdu"}, reachable={"cdu"})
    assert verify_reachable(qdrant, "c") == [_CDU]


def test_an_empty_store_flags_nothing() -> None:
    # Nothing uploaded yet, or everything legitimately retired.
    assert verify_reachable(_Qdrant({}, reachable=set()), "c") == []


def test_points_without_a_vector_path_or_region_are_skipped() -> None:
    """Never flag on incomplete scroll output — that would be a false alarm."""

    class _Partial(_Qdrant):
        def scroll(self, **kwargs):  # noqa: ANN003, ANN201
            return (
                [
                    types.SimpleNamespace(  # no storage_object_path
                        id="1",
                        payload={"party_id": "spd", "region": _REGION},
                        vector={"dense": [0.1] * 8},
                    ),
                    types.SimpleNamespace(  # no vector returned
                        id="2",
                        payload={
                            "meta": {"storage_object_path": _CDU},
                            "party_id": "cdu",
                            "region": _REGION,
                        },
                        vector=None,
                    ),
                    types.SimpleNamespace(  # no region — cannot build the probe filter
                        id="3",
                        payload={
                            "meta": {"storage_object_path": _SPD},
                            "party_id": "spd",
                        },
                        vector={"dense": [0.1] * 8},
                    ),
                ],
                None,
            )

    assert verify_reachable(_Partial({}, reachable=set()), "c") == []

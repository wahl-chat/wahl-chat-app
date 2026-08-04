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
"""

from __future__ import annotations

import types

from src.ingestion.connectors.manifesto_uploads.bulk import verify_reachable

_CTX = "landtagswahl-sachsen-anhalt-2026"
_SPD = f"public/{_CTX}/wahlprogramme/spd/Wahlprogramm-SPD_2026-06-01.pdf"
_CDU = f"public/{_CTX}/wahlprogramme/cdu/Regierungsprogramm-CDU_2026-03-24.pdf"


class _Qdrant:
    """Store whose ANN search reaches only the parties in *reachable*.

    Models the real failure exactly: scroll/count see every point (they read payload),
    while query_points returns nothing for a party whose tenant sub-index is missing.
    """

    def __init__(self, stored: dict[str, str], reachable: set[str]) -> None:
        self._stored = stored  # object_path -> party_id
        self._reachable = reachable
        self.searched: list[str] = []

    def scroll(self, **kwargs):  # noqa: ANN003, ANN201
        points = [
            types.SimpleNamespace(
                id=f"{path}:0",
                payload={"meta": {"storage_object_path": path}, "party_id": party},
                vector={"dense": [0.1] * 8},
            )
            for path, party in self._stored.items()
        ]
        return (points, None)

    def query_points(self, **kwargs):  # noqa: ANN003, ANN201
        conditions = {
            c.key: c.match.value
            for c in getattr(kwargs.get("query_filter"), "must", []) or []
            if getattr(c, "match", None) is not None
        }
        party = conditions.get("party_id")
        self.searched.append(party)
        hit = types.SimpleNamespace(id="x", score=1.0, payload={})
        return types.SimpleNamespace(points=[hit] if party in self._reachable else [])


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


def test_the_probe_is_scoped_to_the_tenant_key() -> None:
    """party_id must be on the filter, or the query would not traverse the same
    tenant sub-index a real retrieval uses — and would miss the very gap it looks for."""
    qdrant = _Qdrant({_SPD: "spd", _CDU: "cdu"}, reachable={"spd", "cdu"})
    verify_reachable(qdrant, "c")
    assert sorted(qdrant.searched) == ["cdu", "spd"]


def test_an_empty_store_flags_nothing() -> None:
    # Nothing uploaded yet, or everything legitimately retired.
    assert verify_reachable(_Qdrant({}, reachable=set()), "c") == []


def test_points_without_a_vector_or_path_are_skipped() -> None:
    """Never flag on incomplete scroll output — that would be a false alarm."""

    class _Partial(_Qdrant):
        def scroll(self, **kwargs):  # noqa: ANN003, ANN201
            return (
                [
                    types.SimpleNamespace(  # no storage_object_path
                        id="1", payload={"party_id": "spd"}, vector={"dense": [0.1] * 8}
                    ),
                    types.SimpleNamespace(  # no vector returned
                        id="2",
                        payload={
                            "meta": {"storage_object_path": _CDU},
                            "party_id": "cdu",
                        },
                        vector=None,
                    ),
                ],
                None,
            )

    assert verify_reachable(_Partial({}, reachable=set()), "c") == []

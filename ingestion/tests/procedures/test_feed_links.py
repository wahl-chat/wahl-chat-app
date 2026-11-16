# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import date

from ingestion.ids import compute_chunk_id, compute_source_item_id
from ingestion.procedures.feed_links import (
    FirestoreProcedures,
    link_feed_items,
    majority_procedures,
    procedure_ids_for_item,
)
from ingestion.procedures.mapper import build_record
from ingestion.procedures.store import ProcedureStore

from .fakes import FakeFirestore, FakeQdrant

TODAY = date(2026, 11, 17)


class _Retrieving(FakeQdrant):
    def retrieve(self, collection_name, ids, with_payload=True, with_vectors=False):
        from .fakes import _Point
        return [_Point(i, self.points[i]) for i in ids if i in self.points]


def _db(vorgaenge, positions) -> FakeFirestore:
    db = FakeFirestore()
    ProcedureStore(db).put(
        build_record(vorgaenge[v], positions[v], previous=None, today=TODAY) for v in ("320784", "338366")
    )
    return db


def test_majority_needs_half_of_the_linked_speeches() -> None:
    assert majority_procedures([["1"], ["1", "2"], ["3"], []]) == ["1"]
    assert majority_procedures([[], []]) == []


def test_a_debate_follows_its_drucksachen(vorgaenge, positions) -> None:
    lookup = FirestoreProcedures(_db(vorgaenge, positions))
    item = {"debate": {"drucksachen": ["21/7860", "21/1"]}}
    assert procedure_ids_for_item(item, lookup=lookup, vote_links={}) == ["338366"]


def test_a_debate_without_drucksachen_follows_its_speeches(vorgaenge, positions) -> None:
    lookup = FirestoreProcedures(_db(vorgaenge, positions))
    item = {"debate": {"drucksachen": []}}
    ids = procedure_ids_for_item(item, lookup=lookup, vote_links={}, speech_links=[["338366"], ["338366"], []])
    assert ids == ["338366"]


def test_a_vote_prefers_its_own_tally_link(vorgaenge, positions) -> None:
    lookup = FirestoreProcedures(_db(vorgaenge, positions))
    item = {"vote": {"poll_id": 5957, "drucksachen": ["21/7860"]}}
    assert procedure_ids_for_item(item, lookup=lookup, vote_links={5957: ["320784"]}) == ["320784"]
    assert procedure_ids_for_item(item, lookup=lookup, vote_links={}) == ["338366"]


def test_stored_items_get_ids_and_summaries(vorgaenge, positions) -> None:
    db = _db(vorgaenge, positions)
    db.collection("feed_items").document("vote-1").set({"parliament": "bundestag", "vote": {"poll_id": 5957}})
    db.collection("feed_items").document("deb-1").set({"parliament": "bundestag", "debate": {"drucksachen": ["21/7860"]}})
    db.collection("feed_items").document("land").set({"parliament": "landtag_st", "debate": {"drucksachen": ["21/7860"]}})
    qdrant = _Retrieving()
    vote_point = str(compute_chunk_id(compute_source_item_id("vote_record", "5957"), 0))
    qdrant.add(vote_point, {"vorgang_ids": ["320784"]})
    n = link_feed_items(db, qdrant, "c", lookup=FirestoreProcedures(db))
    items = db.data["feed_items"]
    assert n == 2
    assert items["vote-1"]["procedure_ids"] == ["320784"]
    assert items["deb-1"]["procedures"][0]["vorgang_id"] == "338366"
    assert items["deb-1"]["procedures"][0]["milestones"]
    assert "procedure_ids" not in items["land"]
    # nothing changed → nothing written
    assert link_feed_items(db, qdrant, "c", lookup=FirestoreProcedures(db)) == 0


def test_a_moved_procedure_refreshes_only_items_pointing_at_it(vorgaenge, positions) -> None:
    db = _db(vorgaenge, positions)
    db.collection("feed_items").document("deb-1").set(
        {"parliament": "bundestag", "debate": {"drucksachen": ["21/7860"]}, "procedure_ids": ["338366"], "procedures": []}
    )
    db.collection("feed_items").document("other").set(
        {"parliament": "bundestag", "debate": {"drucksachen": ["21/1"]}, "procedure_ids": ["1"], "procedures": []}
    )
    n = link_feed_items(db, _Retrieving(), "c", lookup=FirestoreProcedures(db), only_ids={"338366"})
    assert n == 1 and db.data["feed_items"]["deb-1"]["procedures"]
    assert db.data["feed_items"]["other"]["procedures"] == []

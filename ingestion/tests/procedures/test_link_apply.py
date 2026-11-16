# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import date
from typing import Any

from ingestion.procedures.link_apply import Linker, protocol_of
from ingestion.procedures.mapper import build_record

from .conftest import load
from .fakes import FakeDip, FakeQdrant

TODAY = date(2026, 11, 17)
SCHULDENBREMSE_RESULTS = [{"party_id": "cdu", "yes": 300, "no": 6, "abstain": 0},
                          {"party_id": "spd", "yes": 212, "no": 200, "abstain": 0}]


def _vote(qdrant: FakeQdrant, pid: str, *, link: Any = None, day: str = "2025-03-18") -> None:
    payload = {
        "source_type": "vote_record", "source_item_id": "vote-1", "wahlperiode": 20, "region": "DE",
        "publish_date": day, "meta": {"vote_results": SCHULDENBREMSE_RESULTS, "drucksachen": ["20/15096"]},
    }
    if link:
        payload["procedure_link"] = link
    qdrant.add(pid, payload)


def _speech(qdrant: FakeQdrant, pid: str, siid: str, name: str, *, source: str = "op", order: int = 1,
            day: str = "2026-09-08", key: str = "de-21-91-x-top1", link: Any = None) -> None:
    payload = {
        "source_type": "parliamentary_speech", "source": source, "source_item_id": siid, "wahlperiode": 21,
        "region": "DE", "publish_date": day, "speech_key": key,
        "meta": {"speaker_name": name, "origin_media_id": str(order)},
    }
    if link:
        payload["procedure_link"] = link
    qdrant.add(pid, payload)


def _procedures(vorgaenge, positions) -> dict:
    return {vid: build_record(vorgaenge[vid], positions.get(vid, []), previous=None, today=TODAY)
            for vid in ("320784", "338366")}


def _dip(vorgaenge, positions, **kw) -> FakeDip:
    days = {date.fromisoformat(d): p for d, p in load("positions_2025_03_18").items()}
    return FakeDip(vorgaenge, positions, days=days,
                   drucksachen=load("drucksache_vorgaenge_2025_03_18"), **kw)


def _linker(dip, qdrant, procedures, **kw) -> Linker:
    return Linker(dip=dip, qdrant=qdrant, collection="c", procedures=procedures, today=TODAY, **kw)


def test_protocol_of_speech_key() -> None:
    assert protocol_of("de-21-91-stefan-seidler-top12") == "21/91"
    assert protocol_of("de-20-214-tobias-b-bacherle-") == "20/214"
    assert protocol_of(None) is None and protocol_of("x-1-2") is None


def test_a_vote_is_stamped_on_every_chunk_by_exact_id(vorgaenge, positions) -> None:
    qdrant = FakeQdrant()
    _vote(qdrant, "p1")
    _vote(qdrant, "p2")
    linker = _linker(_dip(vorgaenge, positions), qdrant, _procedures(vorgaenge, positions))
    linker.link_votes([20, 21])
    payload, ids = qdrant.payload_writes[0]
    assert sorted(ids) == ["p1", "p2"]
    assert payload["vorgang_ids"] == ["320784"]
    assert payload["procedure_link"] == {"method": "tally_drucksache", "checked_on": "2026-11-17"}
    assert "Öffentliche Finanzen, Steuern und Abgaben" in payload["sachgebiete"]


def test_a_dip_failure_leaves_the_vote_unstamped(vorgaenge, positions) -> None:
    qdrant = FakeQdrant()
    _vote(qdrant, "p1")
    linker = _linker(_dip(vorgaenge, positions, fail={"positions_on"}), qdrant, _procedures(vorgaenge, positions))
    linker.link_votes([20])
    assert not qdrant.payload_writes and linker.report.failed == ["vote-1"]
    assert "procedure_link" not in qdrant.points["p1"]


def test_linked_votes_are_left_alone(vorgaenge, positions) -> None:
    qdrant = FakeQdrant()
    _vote(qdrant, "p1", link={"method": "tally", "checked_on": "2026-11-01"})
    _linker(_dip(vorgaenge, positions), qdrant, _procedures(vorgaenge, positions)).link_votes([20])
    assert not qdrant.payload_writes


def test_only_recent_unlinked_votes_are_checked_again(vorgaenge, positions) -> None:
    qdrant = FakeQdrant()
    _vote(qdrant, "old", link={"method": "none", "checked_on": "2025-03-19"})
    _linker(_dip(vorgaenge, positions), qdrant, _procedures(vorgaenge, positions)).link_votes([20])
    assert not qdrant.payload_writes


def _activities() -> dict[str, list]:
    def act(aid, name, vid, typ="Gesetzgebung", page=11300):
        return {"id": aid, "aktivitaetsart": "Rede", "titel": f"{name}, MdB",
                "fundstelle": {"dokumentnummer": "21/91", "anfangsseite": page, "endseite": page},
                "vorgangsbezug": [{"id": vid, "vorgangstyp": typ}]}
    return {"21/91": [act("a", "Anna Muster", "338366"), act("b", "Ben Frage", "999", "Mündliche Frage"),
                      act("c", "Cora Neu", "555", "Antrag")]}


def test_speeches_link_and_report_out_of_scope_and_unknown(vorgaenge, positions) -> None:
    qdrant = FakeQdrant()
    _speech(qdrant, "s1", "sp-a", "Anna Muster")
    _speech(qdrant, "s2", "sp-b", "Ben Frage")
    _speech(qdrant, "s3", "sp-c", "Cora Neu")
    _speech(qdrant, "s4", "sp-d", "Dora Niemand")
    asked: list[set[str]] = []
    linker = _linker(_dip(vorgaenge, positions, activities=_activities()), qdrant,
                     _procedures(vorgaenge, positions), add_procedures=lambda ids: asked.append(ids) or {})
    linker.link_speeches([21])
    stamped = {pid: qdrant.points[pid]["procedure_link"]["method"] for pid in ("s1", "s2", "s3", "s4")}
    assert stamped == {"s1": "name", "s2": "out_of_scope", "s3": "out_of_scope", "s4": "none"}
    assert qdrant.points["s1"]["vorgang_ids"] == ["338366"]
    assert asked == [{"555"}]  # an unknown in-scope id is synced once
    assert linker.report.missing_procedures == {"555"}


def test_a_failing_protocol_leaves_its_speeches_unstamped(vorgaenge, positions) -> None:
    qdrant = FakeQdrant()
    _speech(qdrant, "s1", "sp-a", "Anna Muster")
    dip = _dip(vorgaenge, positions, activities=_activities(), fail={"activities:21/91"})
    linker = _linker(dip, qdrant, _procedures(vorgaenge, positions))
    linker.link_speeches([21])
    assert "procedure_link" not in qdrant.points["s1"] and linker.report.failed == ["21/91"]


def test_speaking_order_uses_every_speech_of_the_day(vorgaenge, positions) -> None:
    """An already linked earlier speech still counts for the order of a later one."""
    acts = {"21/91": [
        {"id": "1", "aktivitaetsart": "Rede", "titel": "Anna Muster", "fundstelle": {"anfangsseite": 1, "endseite": 1, "dokumentnummer": "21/91"},
         "vorgangsbezug": [{"id": "320784", "vorgangstyp": "Gesetzgebung"}]},
        {"id": "2", "aktivitaetsart": "Rede", "titel": "Anna Muster", "fundstelle": {"anfangsseite": 9, "endseite": 9, "dokumentnummer": "21/91"},
         "vorgangsbezug": [{"id": "338366", "vorgangstyp": "Gesetzgebung"}]},
    ]}
    qdrant = FakeQdrant()
    _speech(qdrant, "early", "sp-1", "Anna Muster", order=1, link={"method": "name_order", "checked_on": "2026-11-01"})
    _speech(qdrant, "late", "sp-2", "Anna Muster", order=2)
    _linker(_dip(vorgaenge, positions, activities=acts), qdrant, _procedures(vorgaenge, positions)).link_speeches([21])
    assert qdrant.points["late"]["vorgang_ids"] == ["338366"]
    assert qdrant.points["early"]["procedure_link"]["checked_on"] == "2026-11-01"


def test_changed_topics_flow_down_to_linked_chunks(vorgaenge, positions) -> None:
    qdrant = FakeQdrant()
    _speech(qdrant, "s1", "sp-a", "Anna Muster", link={"method": "name", "checked_on": "2026-11-01"})
    qdrant.points["s1"]["vorgang_ids"] = ["338366"]
    procedures = _procedures(vorgaenge, positions)
    procedures["338366"] = procedures["338366"].model_copy(update={"sachgebiete": ["Neu"]})
    _linker(_dip(vorgaenge, positions), qdrant, procedures).refresh_sachgebiete(["338366"])
    assert qdrant.points["s1"]["sachgebiete"] == ["Neu"]
    assert qdrant.points["s1"]["procedure_link"]["method"] == "name"

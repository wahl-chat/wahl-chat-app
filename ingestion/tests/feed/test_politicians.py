# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import pytest

from ingestion.feed import politician_sources as s
from ingestion.feed import politicians as p
from ingestion.feed.builder import FeedBuilder
from ingestion.feed.models import DebateFacts, DebateParty, DigestSpeaker, FeedItem
from ingestion.feed.prompts import (
    POLITICIAN_TRANSLATION_PROMPT_VERSION,
    TranslatedSegment,
    TranslationBatch,
)

from tests.feed.politician_samples import (
    INDEX,
    VOTES,
    profile_xml,
    roll_call_list,
    write_stammdaten,
)

NOW = datetime(2026, 11, 11, tzinfo=timezone.utc)


@pytest.fixture
def stammdaten(tmp_path: Path) -> Path:
    return write_stammdaten(tmp_path)


class FakeSnapshot:
    def __init__(self, doc_id: str, data: Optional[dict]) -> None:
        self.id = doc_id
        self.exists = data is not None
        self._data = data

    def to_dict(self) -> Optional[dict]:
        return self._data


class FakeRef:
    def __init__(self, db: "FakeDb", doc_id: str) -> None:
        self._db = db
        self.id = doc_id

    def set(self, data: dict) -> None:
        self._db.docs[self.id] = data


class FakeDb:
    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}

    def collection(self, name: str) -> Any:
        assert name == p.POLITICIAN_COLLECTION
        return self

    def document(self, doc_id: str) -> FakeRef:
        return FakeRef(self, doc_id)

    def get_all(self, refs: list[FakeRef]) -> list[FakeSnapshot]:
        return [FakeSnapshot(r.id, self.docs.get(r.id)) for r in refs]


def _fetcher(pages: dict[str, str], log: Optional[list[str]] = None) -> s.Fetch:
    def fetch(url: str) -> str:
        if log is not None:
            log.append(url)
        if url not in pages:
            raise OSError(f"unreachable: {url}")
        return pages[url]

    return fetch


def _pages(newest: str = "15. Oktober 2026", **profiles: str) -> dict[str, str]:
    """The index, the roll-call list, and these profiles; the namesake's is
    always there, and the votes of the member's own profile."""
    profiles = {"9999": profile_xml("9999", "01.01.1970"), **profiles}
    return {
        s.INDEX_URL: INDEX,
        s.ROLL_CALL_LIST_URL: roll_call_list(newest),
        s.VOTES_URL.format(bio_id="2314"): VOTES,
        **{s.PROFILE_URL.format(bio_id=k): v for k, v in profiles.items()},
    }


def _refresh(
    db: FakeDb, ids: list[str], stammdaten: Path, fetch: s.Fetch, **kwargs: Any
) -> p.RefreshReport:
    return p.refresh_politicians(
        db,
        ids,
        fetch=fetch,
        stammdaten=lambda due: s.read_stammdaten(stammdaten, due),
        now=kwargs.pop("now", NOW),
        pause=lambda: None,
        **kwargs,
    )


def test_a_namesake_is_told_apart_by_birth_date(stammdaten: Path) -> None:
    db = FakeDb()
    log: list[str] = []
    fetch = _fetcher(_pages(**{"2314": profile_xml()}), log)
    report = _refresh(db, ["11005000"], stammdaten, fetch)
    # The namesake comes first in the index and is ruled out.
    assert log == [
        s.INDEX_URL,
        s.ROLL_CALL_LIST_URL,
        s.PROFILE_URL.format(bio_id="9999"),
        s.PROFILE_URL.format(bio_id="2314"),
        s.VOTES_URL.format(bio_id="2314"),
    ]
    assert report.written == ["11005000"]
    stored = p.Politician.model_validate(db.docs["11005000"])
    assert stored.bio_id == "2314"
    assert stored.last_changed == "07.10.2026 14:32"
    assert stored.offices[0].function == "Parlamentarische Staatssekretärin"
    assert stored.disclosures is not None


def test_an_unreadable_namesake_does_not_hide_the_rightprofile(
    stammdaten: Path,
) -> None:
    pages = _pages(**{"2314": profile_xml()})
    del pages[s.PROFILE_URL.format(bio_id="9999")]
    db = FakeDb()
    assert _refresh(db, ["11005000"], stammdaten, _fetcher(pages)).written == [
        "11005000"
    ]
    assert db.docs["11005000"]["bio_id"] == "2314"


def test_an_unchanged_profile_is_not_fetched_again(stammdaten: Path) -> None:
    db = FakeDb()
    _refresh(db, ["11005000"], stammdaten, _fetcher(_pages(**{"2314": profile_xml()})))
    log: list[str] = []
    report = _refresh(db, ["11005000"], stammdaten, _fetcher(_pages(), log))
    assert report.written == []
    assert log == [s.INDEX_URL, s.ROLL_CALL_LIST_URL]


def test_a_changed_profile_is_fetched_by_its_known_id(stammdaten: Path) -> None:
    db = FakeDb()
    _refresh(db, ["11005000"], stammdaten, _fetcher(_pages(**{"2314": profile_xml()})))
    db.docs["11005000"]["last_changed"] = "01.01.2026 00:00"
    log: list[str] = []
    fetch = _fetcher(_pages(**{"2314": profile_xml()}), log)
    assert _refresh(db, ["11005000"], stammdaten, fetch).written == ["11005000"]
    assert log == [
        s.INDEX_URL,
        s.ROLL_CALL_LIST_URL,
        s.PROFILE_URL.format(bio_id="2314"),
        s.VOTES_URL.format(bio_id="2314"),
    ]


def test_a_member_without_a_profile_is_stored_from_the_stammdaten_and_retried_monthly(
    stammdaten: Path,
) -> None:
    db = FakeDb()
    assert _refresh(db, ["11001478"], stammdaten, _fetcher(_pages())).written == [
        "11001478"
    ]
    stored = p.Politician.model_validate(db.docs["11001478"])
    assert (stored.name, stored.bio_id, stored.memberships) == (
        "Angela Merkel",
        None,
        [],
    )
    assert [t.wp for t in stored.terms] == [19]
    soon = NOW + timedelta(days=1)
    later = NOW + p.RECHECK_AFTER
    assert (
        _refresh(db, ["11001478"], stammdaten, _fetcher(_pages()), now=soon).written
        == []
    )
    assert _refresh(
        db, ["11001478"], stammdaten, _fetcher(_pages()), now=later
    ).written == ["11001478"]


def test_speakers_outside_the_stammdaten_and_failures_are_skipped(
    stammdaten: Path,
) -> None:
    db = FakeDb()
    # Their profile cannot be fetched: logged, not raised, retried next run.
    report = _refresh(db, ["99999999", "11005000"], stammdaten, _fetcher(_pages()))
    assert report.not_members == ["99999999"]
    assert report.failed == ["11005000"]
    assert db.docs == {}


def test_a_spent_budget_sends_no_request_at_all(stammdaten: Path) -> None:
    log: list[str] = []
    report = _refresh(
        FakeDb(),
        ["11005000"],
        stammdaten,
        _fetcher(_pages(**{"2314": profile_xml()}), log),
        out_of_time=lambda: True,
    )
    assert report.out_of_time
    assert (report.written, log) == ([], [])


def test_a_budget_spent_after_the_index_stops_before_the_members(
    stammdaten: Path,
) -> None:
    checks = iter([False, False, True])
    log: list[str] = []
    report = _refresh(
        FakeDb(),
        ["11005000"],
        stammdaten,
        _fetcher(_pages(**{"2314": profile_xml()}), log),
        out_of_time=lambda: next(checks, True),
    )
    assert report.out_of_time
    assert report.written == []
    assert log == [s.INDEX_URL, s.ROLL_CALL_LIST_URL]


def test_speaker_ids_come_from_every_debate_once() -> None:
    def item(item_id: str, *ids: Optional[str]) -> FeedItem:
        return FeedItem.model_construct(
            id=item_id,
            debate=DebateFacts.model_construct(
                parties=[
                    DebateParty.model_construct(
                        speakers=[DigestSpeaker(name=f"n{i}", mdb_id=i) for i in ids]
                    )
                ]
            ),
        )

    items = [
        item("a", "1", None, "2"),
        item("b", "2", "3"),
        FeedItem.model_construct(debate=None),
    ]
    assert p.speaker_ids(items) == ["1", "2", "3"]


def test_a_newer_vote_refreshes_only_the_votes(stammdaten: Path) -> None:
    db = FakeDb()
    _refresh(db, ["11005000"], stammdaten, _fetcher(_pages(**{"2314": profile_xml()})))
    assert len(db.docs["11005000"]["votes"]) == 3

    # A vote the morning after the stored list was read.
    morning = datetime(2026, 11, 13, 6, tzinfo=timezone.utc)
    log: list[str] = []
    fetch = _fetcher(_pages("12. November 2026"), log)
    report = _refresh(db, ["11005000"], stammdaten, fetch, now=morning)
    assert report.written == ["11005000"]
    assert log == [
        s.INDEX_URL,
        s.ROLL_CALL_LIST_URL,
        s.VOTES_URL.format(bio_id="2314"),
    ]
    stored = p.Politician.model_validate(db.docs["11005000"])
    assert stored.votes_checked_at == morning
    # The rest of the record stays as read.
    assert stored.fetched_at == NOW

    # Read since that vote: nothing to do the next day.
    next_day = morning + timedelta(days=1)
    fetch = _fetcher(_pages("12. November 2026"))
    assert _refresh(db, ["11005000"], stammdaten, fetch, now=next_day).written == []


def test_an_unreadable_vote_list_falls_back_to_the_votes_age(
    stammdaten: Path,
) -> None:
    db = FakeDb()
    _refresh(db, ["11005000"], stammdaten, _fetcher(_pages(**{"2314": profile_xml()})))
    pages = _pages()
    del pages[s.ROLL_CALL_LIST_URL]
    soon = NOW + timedelta(days=1)
    later = NOW + p.VOTES_FALLBACK_AGE
    assert (
        _refresh(db, ["11005000"], stammdaten, _fetcher(pages), now=soon).written == []
    )
    assert _refresh(
        db, ["11005000"], stammdaten, _fetcher(pages), now=later
    ).written == ["11005000"]


def test_unreadable_stammdaten_skip_new_members_but_not_the_votes(
    stammdaten: Path,
) -> None:
    db = FakeDb()
    _refresh(db, ["11005000"], stammdaten, _fetcher(_pages(**{"2314": profile_xml()})))

    def unreadable(_: list[str]) -> dict[str, s.StammProfile]:
        raise OSError("bundestag.de did not answer")

    morning = datetime(2026, 11, 13, 6, tzinfo=timezone.utc)
    log: list[str] = []
    report = p.refresh_politicians(
        db,
        ["11005000", "11001478"],
        fetch=_fetcher(_pages("12. November 2026"), log),
        stammdaten=unreadable,
        now=morning,
        pause=lambda: None,
    )
    # The new member is tried again next run; the stored one gets its votes.
    assert report.failed == ["11001478"]
    assert report.written == ["11005000"]
    assert log[-1] == s.VOTES_URL.format(bio_id="2314")


def test_a_member_who_left_keeps_the_votes_last_read(stammdaten: Path) -> None:
    db = FakeDb()
    _refresh(db, ["11005000"], stammdaten, _fetcher(_pages(**{"2314": profile_xml()})))
    pages = _pages("12. November 2026")
    # Only the namesake is left in the index.
    pages[s.INDEX_URL] = (
        INDEX.split('<mdb fraktion="SPD">')[0] + "</mdbs></mdbUebersicht>"
    )
    log: list[str] = []
    morning = datetime(2026, 11, 13, 6, tzinfo=timezone.utc)
    report = _refresh(db, ["11005000"], stammdaten, _fetcher(pages, log), now=morning)
    assert report.written == []
    assert log == [s.INDEX_URL, s.ROLL_CALL_LIST_URL]
    assert len(db.docs["11005000"]["votes"]) == 3


def test_an_empty_vote_page_keeps_the_stored_votes(stammdaten: Path) -> None:
    db = FakeDb()
    _refresh(db, ["11005000"], stammdaten, _fetcher(_pages(**{"2314": profile_xml()})))
    pages = _pages("12. November 2026")
    pages[s.VOTES_URL.format(bio_id="2314")] = "<table><tbody></tbody></table>"
    morning = datetime(2026, 11, 13, 6, tzinfo=timezone.utc)
    assert _refresh(db, ["11005000"], stammdaten, _fetcher(pages), now=morning).written
    stored = p.Politician.model_validate(db.docs["11005000"])
    assert len(stored.votes) == 3
    # Checked, so a page that stays broken is not fetched on every run.
    assert stored.votes_checked_at == morning


def test_unreadable_votes_keep_the_profile(stammdaten: Path) -> None:
    db = FakeDb()
    pages = _pages(**{"2314": profile_xml()})
    del pages[s.VOTES_URL.format(bio_id="2314")]
    report = _refresh(db, ["11005000"], stammdaten, _fetcher(pages))
    assert (report.written, report.failed) == (["11005000"], [])
    stored = p.Politician.model_validate(db.docs["11005000"])
    assert (stored.bio_id, stored.votes, stored.votes_checked_at) == ("2314", [], None)

    # The next run reads only the votes.
    log: list[str] = []
    later = NOW + timedelta(hours=1)
    fetch = _fetcher(_pages(), log)
    assert _refresh(db, ["11005000"], stammdaten, fetch, now=later).written
    assert log == [
        s.INDEX_URL,
        s.ROLL_CALL_LIST_URL,
        s.VOTES_URL.format(bio_id="2314"),
    ]


def test_an_unchanged_profile_is_read_again_after_a_month(stammdaten: Path) -> None:
    db = FakeDb()
    _refresh(db, ["11005000"], stammdaten, _fetcher(_pages(**{"2314": profile_xml()})))
    log: list[str] = []
    later = NOW + p.RECHECK_AFTER
    fetch = _fetcher(_pages("15. Oktober 2026", **{"2314": profile_xml()}), log)
    assert _refresh(db, ["11005000"], stammdaten, fetch, now=later).written
    assert s.PROFILE_URL.format(bio_id="2314") in log
    stored = p.Politician.model_validate(db.docs["11005000"])
    assert stored.fetched_at == later
    assert len(stored.votes) == 3


def test_a_field_the_model_dropped_does_not_make_a_record_due(
    stammdaten: Path,
) -> None:
    db = FakeDb()
    _refresh(db, ["11005000"], stammdaten, _fetcher(_pages(**{"2314": profile_xml()})))
    db.docs["11005000"]["retired_field"] = "kept until the next write"
    log: list[str] = []
    assert _refresh(db, ["11005000"], stammdaten, _fetcher(_pages(), log)).written == []
    assert log == [s.INDEX_URL, s.ROLL_CALL_LIST_URL]


def test_a_minister_from_outside_the_bundestag_gets_a_record_from_the_roster(
    stammdaten: Path,
) -> None:
    from ingestion.feed.speaker_parties import OutsideSpeaker, Roster

    roster = Roster(
        [
            OutsideSpeaker(
                name="Karsten Wildberger",
                party="CDU",
                office="Bundesminister für Digitales und Staatsmodernisierung",
                institution="Bundesregierung",
            ),
            OutsideSpeaker(
                name="Ronald Rauhe",
                party=None,
                office="Staatsminister für Sport und Ehrenamt",
                institution="Bundesregierung",
            ),
        ]
    )
    db = FakeDb()
    report = _refresh(
        db,
        ["999990160", "999990170", "99999999"],
        stammdaten,
        _fetcher(_pages()),
        roster=lambda: roster,
        names={"999990160": "Dr. Karsten Wildberger", "999990170": "Ronald Rauhe"},
    )
    assert report.written == ["999990160", "999990170"]
    # No official source names his party, so his record names none.
    assert db.docs["999990170"]["partei"] is None
    assert report.not_members == ["99999999"]
    record = db.docs["999990160"]
    assert (record["name"], record["partei"], record["source"]) == (
        "Karsten Wildberger",
        "CDU",
        "roster",
    )
    assert record["offices"] == [
        {
            "function": "Bundesminister für Digitales und Staatsmodernisierung",
            "institution": "Bundesregierung",
            "kind": "government",
        }
    ]


# --- translation -------------------------------------------------------------


class Translator:
    """Answers each segment with ``EN <German>``, unless ``edit`` says
    otherwise; records every German text it was sent."""

    def __init__(
        self, edit: Optional[dict[str, str]] = None, fail: bool = False
    ) -> None:
        self.edit = edit or {}
        self.fail = fail
        self.sent: list[str] = []

    async def __call__(self, messages: list, schema: type) -> tuple[Any, str]:
        assert schema is TranslationBatch
        if self.fail:
            raise RuntimeError("quota")
        segments = []
        for ref, german in re.findall(
            r"^\[(S\d+)\] (.*)$", messages[0].content, re.MULTILINE
        ):
            self.sent.append(german)
            segments.append(
                TranslatedSegment(ref=ref, text=self.edit.get(german, f"EN {german}"))
            )
        return TranslationBatch(segments=segments), "fake-translator"


def _translated_refresh(
    db: FakeDb,
    ids: list[str],
    stammdaten: Path,
    fetch: s.Fetch,
    translator: Translator,
    **kwargs: Any,
) -> p.RefreshReport:
    builder = FeedBuilder(translator)
    try:
        return _refresh(db, ids, stammdaten, fetch, builder=builder, **kwargs)
    finally:
        builder.close()


def _english(record: p.Politician) -> dict[str, str]:
    return {t.source: t.text for t in record.translations["en"].texts}


def test_a_new_record_is_written_with_its_english(stammdaten: Path) -> None:
    db = FakeDb()
    translator = Translator()
    fetch = _fetcher(_pages(**{"2314": profile_xml()}))
    report = _translated_refresh(db, ["11005000"], stammdaten, fetch, translator)
    assert report.written == ["11005000"]
    record = p.Politician.model_validate(db.docs["11005000"])
    english = _english(record)
    texts = p.display_texts(record)
    assert set(english) == set(texts)
    assert all(english[t] == f"EN {t}" for t in texts)
    for german in (
        "Parlamentarische Staatssekretärin",
        "Bundesministerium der Finanzen",
        "Ausschuss für wirtschaftliche Zusammenarbeit und Entwicklung",
        "Obfrau",
        "Vertrags- und Finanzmanagerin",
        "Änderung des Brennstoffemissionshandelsgesetzes",
        "Individuelle Erläuterungen",
    ):
        assert german in english, german
    # Proper names stay as published and are never sent.
    assert not {"Sanae Abdi", "SPD", "Köln I"} & set(translator.sent)
    # Each distinct text once, though the Gremium is listed twice.
    assert len(translator.sent) == len(set(translator.sent))
    translation = record.translations["en"]
    assert translation.source_hash == p.texts_hash(record)
    assert translation.prompt_version == POLITICIAN_TRANSLATION_PROMPT_VERSION
    assert not p.needs_politician_translation(record, "en")


def test_a_current_record_costs_no_translation(stammdaten: Path) -> None:
    db = FakeDb()
    fetch = _fetcher(_pages(**{"2314": profile_xml()}))
    _translated_refresh(db, ["11005000"], stammdaten, fetch, Translator())
    translator = Translator()
    report = _translated_refresh(
        db, ["11005000"], stammdaten, _fetcher(_pages()), translator
    )
    assert (report.written, translator.sent) == ([], [])


def test_a_stored_record_without_english_is_translated_without_a_fetch(
    stammdaten: Path,
) -> None:
    db = FakeDb()
    _refresh(db, ["11005000"], stammdaten, _fetcher(_pages(**{"2314": profile_xml()})))
    assert db.docs["11005000"]["translations"] == {}
    log: list[str] = []
    report = _translated_refresh(
        db, ["11005000"], stammdaten, _fetcher(_pages(), log), Translator()
    )
    assert report.written == ["11005000"]
    assert log == [s.INDEX_URL, s.ROLL_CALL_LIST_URL]
    record = p.Politician.model_validate(db.docs["11005000"])
    assert set(_english(record)) == set(p.display_texts(record))


def test_a_new_vote_is_translated_and_the_known_texts_are_not_sent_again(
    stammdaten: Path,
) -> None:
    db = FakeDb()
    fetch = _fetcher(_pages(**{"2314": profile_xml()}))
    _translated_refresh(db, ["11005000"], stammdaten, fetch, Translator())
    pages = _pages("12. November 2026")
    pages[s.VOTES_URL.format(bio_id="2314")] = VOTES.replace(
        "Cum-Cum", "Gesetz zur Modernisierung des Wehrdienstes"
    )
    translator = Translator()
    morning = datetime(2026, 11, 13, 6, tzinfo=timezone.utc)
    _translated_refresh(
        db, ["11005000"], stammdaten, _fetcher(pages), translator, now=morning
    )
    assert translator.sent == ["Gesetz zur Modernisierung des Wehrdienstes"]
    record = p.Politician.model_validate(db.docs["11005000"])
    assert "Cum-Cum" not in _english(record)
    assert not p.needs_politician_translation(record, "en")


def test_a_stale_translation_is_renewed(stammdaten: Path) -> None:
    db = FakeDb()
    fetch = _fetcher(_pages(**{"2314": profile_xml()}))
    _translated_refresh(db, ["11005000"], stammdaten, fetch, Translator())
    db.docs["11005000"]["translations"]["en"]["source_hash"] = "older texts"
    db.docs["11005000"]["translations"]["en"]["prompt_version"] = "0"
    translator = Translator()
    report = _translated_refresh(
        db, ["11005000"], stammdaten, _fetcher(_pages()), translator
    )
    assert report.written == ["11005000"]
    record = p.Politician.model_validate(db.docs["11005000"])
    assert record.translations["en"].source_hash == p.texts_hash(record)
    assert not p.needs_politician_translation(record, "en")


def test_a_text_that_fails_its_check_stays_german_and_is_retried(
    stammdaten: Path,
) -> None:
    db = FakeDb()
    title = "Antrag zur Kassenzulassung des nicht-invasiven Pränataltests"
    # Runs on far past its German text.
    translator = Translator({title: "EN " + "very " * 60 + "long"})
    fetch = _fetcher(_pages(**{"2314": profile_xml()}))
    _translated_refresh(db, ["11005000"], stammdaten, fetch, translator)
    record = p.Politician.model_validate(db.docs["11005000"])
    english = _english(record)
    assert title not in english
    assert english["Obfrau"] == "EN Obfrau"
    assert p.needs_politician_translation(record, "en")

    retry = Translator()
    _translated_refresh(db, ["11005000"], stammdaten, _fetcher(_pages()), retry)
    assert retry.sent == [title]
    record = p.Politician.model_validate(db.docs["11005000"])
    assert not p.needs_politician_translation(record, "en")


def test_a_failed_translation_call_still_writes_the_record(stammdaten: Path) -> None:
    db = FakeDb()
    fetch = _fetcher(_pages(**{"2314": profile_xml()}))
    report = _translated_refresh(
        db, ["11005000"], stammdaten, fetch, Translator(fail=True)
    )
    assert report.written == ["11005000"]
    assert db.docs["11005000"]["translations"] == {}
    # The next run fills it in without reading bundestag.de again.
    assert _translated_refresh(
        db, ["11005000"], stammdaten, _fetcher(_pages()), Translator()
    ).written == ["11005000"]


def test_a_record_read_again_keeps_its_english_while_translation_fails(
    stammdaten: Path,
) -> None:
    db = FakeDb()
    fetch = _fetcher(_pages(**{"2314": profile_xml()}))
    _translated_refresh(db, ["11005000"], stammdaten, fetch, Translator())
    later = NOW + p.RECHECK_AFTER
    fetch = _fetcher(_pages(**{"2314": profile_xml()}))
    _translated_refresh(
        db, ["11005000"], stammdaten, fetch, Translator(fail=True), now=later
    )
    record = p.Politician.model_validate(db.docs["11005000"])
    assert _english(record)["Obfrau"] == "EN Obfrau"


def test_stored_records_are_translated_without_reading_bundestag_de(
    stammdaten: Path,
) -> None:
    db = FakeDb()
    _refresh(db, ["11005000"], stammdaten, _fetcher(_pages(**{"2314": profile_xml()})))
    builder = FeedBuilder(Translator())
    try:
        written = p.translate_stored_politicians(
            db, ["11005000", "missing"], builder, now=NOW
        )
        assert written == ["11005000"]
        assert p.translate_stored_politicians(db, ["11005000"], builder) == []
    finally:
        builder.close()

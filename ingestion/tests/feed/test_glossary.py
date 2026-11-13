# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import re
from datetime import datetime, timezone
from typing import Any, Optional

from ingestion.feed.builder import FeedBuilder
from ingestion.feed.glossary import (
    MAX_DEFINITION_ATTEMPTS,
    GlossaryEntry,
    annotate_terms,
    needs_terms,
    term_id,
)
from ingestion.feed.glossary_sources import GlossarySource, Research
from ingestion.feed.models import FeedItem
from ingestion.feed.prompts import (
    GLOSSARY_PROMPT_VERSION,
    DefinitionCheck,
    DefinitionCheckBatch,
    FormCheck,
    FormCheckBatch,
    ItemTerms,
    TermDefinition,
    TermDefinitionBatch,
    TermDraft,
    TermExtractionBatch,
)
from tests.feed.samples import sample_items

NOW = datetime(2026, 11, 12, 8, tzinfo=timezone.utc)
_REF_RE = re.compile(r"^\[([TB]\d+)\]", re.MULTILINE)
_PAGE = "https://www.bundestag.de/services/glossar/{slug}"


def _page_url(term: str) -> str:
    return _PAGE.format(slug=term_id(term))


class GlossaryLLM:
    """Names the terms it is given for every text, accepts every form but
    those it is told to reject, defines each term citing its first source,
    and passes every definition but those it is told to reject. ``omit``
    leaves a term out of an answer, as a model sometimes does."""

    def __init__(
        self,
        terms: list[tuple[str, str]],
        *,
        reject: tuple[str, ...] = (),
        reject_forms: tuple[str, ...] = (),
        cite_nothing: tuple[str, ...] = (),
        omit: tuple[tuple[type, str], ...] = (),
        fail: tuple[type, ...] = (),
    ) -> None:
        self.terms = terms
        self.reject = reject
        self.reject_forms = reject_forms
        self.cite_nothing = cite_nothing
        self.omit = omit
        self.fail = fail
        self.calls: list[type] = []
        self.prompts: dict[type, list[str]] = {}

    def _omitted(self, schema: type, name: str) -> bool:
        return (schema, name) in self.omit

    async def __call__(self, messages: list, schema: type) -> tuple[Any, str]:
        self.calls.append(schema)
        prompt = messages[0].content
        self.prompts.setdefault(schema, []).append(prompt)
        if schema in self.fail:
            raise RuntimeError("quota")
        if schema is TermExtractionBatch:
            return TermExtractionBatch(
                items=[
                    ItemTerms(
                        ref=ref,
                        terms=[TermDraft(surface=s, term=t) for s, t in self.terms],
                    )
                    for ref in _REF_RE.findall(prompt)
                ]
            ), "fake-model"
        if schema is FormCheckBatch:
            rows = re.findall(r"^\[(F\d+)\] „(.+?)“ → „(.+?)“", prompt, re.MULTILINE)
            return FormCheckBatch(
                checks=[
                    FormCheck(ref=ref, reason="-", ok=surface not in self.reject_forms)
                    for ref, surface, _ in rows
                    if not self._omitted(schema, surface)
                ]
            ), "fake-model"
        if schema is TermDefinitionBatch:
            terms = re.findall(r"^\[(B\d+)\] (.+)$", prompt, re.MULTILINE)
            return TermDefinitionBatch(
                definitions=[
                    TermDefinition(
                        ref=ref,
                        definition=f"{term} erklärt.",
                        sources=[] if term in self.cite_nothing else [f"{ref}-Q1"],
                    )
                    for ref, term in terms
                    if not self._omitted(schema, term)
                ]
            ), "fake-model"
        if schema is DefinitionCheckBatch:
            lines = re.findall(r"^\[([BH]\d+)\] (.+?):", prompt, re.MULTILINE)
            return DefinitionCheckBatch(
                checks=[
                    DefinitionCheck(ref=ref, reason="-", ok=term not in self.reject)
                    for ref, term in lines
                    if not self._omitted(schema, term)
                ]
            ), "fake-model"
        raise AssertionError(f"unexpected schema {schema}")


class Search:
    """Finds one Bundestag glossary page per term, or none for the terms it
    is told about."""

    def __init__(
        self, *, nothing_for: tuple[str, ...] = (), fail: bool = False
    ) -> None:
        self.nothing_for = nothing_for
        self.fail = fail
        self.searched: list[str] = []

    async def __call__(self, parliament: str, term: str, context: str) -> Research:
        self.searched.append(term)
        if self.fail:
            raise RuntimeError("search unavailable")
        if term in self.nothing_for:
            return Research(notes="", sources=[])
        return Research(
            notes=f"{term}: siehe Glossar.",
            sources=[GlossarySource(url=_page_url(term), title="bundestag.de")],
        )


def _fetch(url: str) -> str:
    return (
        "<html><head><title>Glossar - Deutscher Bundestag</title></head>"
        f"<body><nav>Menü</nav><p>Erklärung zu {url}.</p></body></html>"
    )


def _unreachable(url: str) -> str:
    raise OSError("bundestag.de unreachable")


def _debate(teaser: str) -> FeedItem:
    item = next(i for i in sample_items() if i.debate is not None)
    item.content["de"].teaser = teaser
    return item


def _run(
    llm: GlossaryLLM,
    items: list[FeedItem],
    glossary: Optional[dict[str, GlossaryEntry]] = None,
    *,
    search: Optional[Search] = None,
    fetch: Any = _fetch,
) -> tuple[list[FeedItem], list[GlossaryEntry], dict[str, GlossaryEntry]]:
    glossary = {} if glossary is None else glossary
    builder = FeedBuilder(llm)
    try:
        changed, entries, _ = annotate_terms(
            items,
            builder,
            glossary,
            now=NOW,
            research=search or Search(),
            fetch=fetch,
        )
    finally:
        builder.close()
    return changed, entries, glossary


def _entry(term: str, **fields: Any) -> GlossaryEntry:
    values: dict[str, Any] = {
        "term_id": term_id(term),
        "term": term,
        "definition": f"{term} erklärt.",
        "forms": [term],
        "sources": [GlossarySource(url=_page_url(term), title="Glossar")],
        "status": "verified",
        "attempts": 1,
        "generated_by": "fake-model",
        "prompt_version": GLOSSARY_PROMPT_VERSION,
        "updated_at": NOW,
    }
    values.update(fields)
    return GlossaryEntry(**values)


# --- find -------------------------------------------------------------------


def test_terms_are_found_defined_from_their_sources_checked_and_stored() -> None:
    item = _debate("In einer Aktuellen Stunde ging es um die Bahn.")
    llm = GlossaryLLM([("Aktuellen Stunde", "Aktuelle Stunde")])
    changed, entries, glossary = _run(llm, [item])
    assert changed == [item]
    [ref] = item.content["de"].terms
    assert (ref.term_id, ref.surface) == ("aktuelle-stunde", "Aktuellen Stunde")
    assert not needs_terms(item)
    [entry] = entries
    assert entry.status == "verified"
    assert entry.definition == "Aktuelle Stunde erklärt."
    assert entry.forms == ["Aktuelle Stunde", "Aktuellen Stunde"]
    # Titled as the page titles itself, not as the search named it.
    assert entry.sources == [
        GlossarySource(
            url=_page_url("Aktuelle Stunde"), title="Glossar - Deutscher Bundestag"
        )
    ]
    assert entry.prompt_version == GLOSSARY_PROMPT_VERSION
    assert glossary["aktuelle-stunde"] is entry
    # The definition is written from the page's text, and checked against it.
    for schema in (TermDefinitionBatch, DefinitionCheckBatch):
        [prompt] = llm.prompts[schema]
        assert f"Erklärung zu {_page_url('Aktuelle Stunde')}" in prompt
        assert "Menü" not in prompt


def test_a_term_not_in_the_text_is_dropped() -> None:
    item = _debate("Der Bundestag beriet über die Bahn.")
    llm = GlossaryLLM([("Aktuellen Stunde", "Aktuelle Stunde")])
    _, entries, _ = _run(llm, [item])
    assert item.content["de"].terms == []
    assert entries == []
    # Looked at, so not asked about again until the text changes.
    assert not needs_terms(item)


def test_a_term_inside_another_word_is_dropped() -> None:
    item = _debate("Der Stundenlohn steigt.")
    llm = GlossaryLLM([("Stunde", "Stunde")])
    _, entries, _ = _run(llm, [item])
    assert item.content["de"].terms == []
    assert entries == []


def test_a_form_that_is_another_term_is_never_stored() -> None:
    item = _debate("Der Ausschuss hat beraten.")
    llm = GlossaryLLM(
        [("Ausschuss", "Petitionsausschuss")], reject_forms=("Ausschuss",)
    )
    known = _entry("Petitionsausschuss")
    _, _, glossary = _run(llm, [item], {"petitionsausschuss": known})
    assert item.content["de"].terms == []
    assert glossary["petitionsausschuss"].forms == ["Petitionsausschuss"]
    # Checked once: the item is settled until its text changes.
    assert not needs_terms(item)
    # The check saw the sentence the form stood in.
    [prompt] = llm.prompts[FormCheckBatch]
    assert "Satz: „Der Ausschuss hat beraten.“" in prompt


def test_a_form_the_check_leaves_unanswered_keeps_the_item_for_the_next_run() -> None:
    item = _debate("In einer Aktuellen Stunde ging es um die Bahn.")
    llm = GlossaryLLM(
        [("Aktuellen Stunde", "Aktuelle Stunde")],
        omit=((FormCheckBatch, "Aktuellen Stunde"),),
    )
    changed, _, glossary = _run(llm, [item])
    assert changed == []
    assert needs_terms(item)
    assert "aktuelle-stunde" not in glossary


def test_a_checked_form_is_not_checked_again() -> None:
    item = _debate("In einer Aktuellen Stunde ging es um die Bahn.")
    known = _entry("Aktuelle Stunde", forms=["Aktuelle Stunde", "Aktuellen Stunde"])
    llm = GlossaryLLM([("Aktuellen Stunde", "Aktuelle Stunde")])
    _, entries, _ = _run(llm, [item], {"aktuelle-stunde": known})
    assert FormCheckBatch not in llm.calls
    assert [r.surface for r in item.content["de"].terms] == ["Aktuellen Stunde"]
    assert entries == []


def test_a_failed_call_leaves_the_item_for_the_next_run() -> None:
    item = _debate("In einer Aktuellen Stunde ging es um die Bahn.")
    llm = GlossaryLLM(
        [("Aktuellen Stunde", "Aktuelle Stunde")], fail=(TermExtractionBatch,)
    )
    changed, entries, _ = _run(llm, [item])
    assert (changed, entries) == ([], [])
    assert needs_terms(item)


def test_an_office_gets_its_term_explained_without_a_ref_on_the_item() -> None:
    item = _debate("Die Bahn soll pünktlicher werden.")
    assert item.debate is not None
    speaker = item.debate.parties[0].speakers[0]
    item.debate.parties[0].speakers[0] = speaker.model_copy(
        update={
            "role": "Parlamentarische Staatssekretärin beim Bundesminister für Verkehr"
        }
    )
    llm = GlossaryLLM(
        [("Parlamentarische Staatssekretärin", "Parlamentarischer Staatssekretär")]
    )
    _, _, glossary = _run(llm, [item])
    assert item.content["de"].terms == []
    entry = glossary["parlamentarischer-staatssekretaer"]
    assert "Parlamentarische Staatssekretärin" in entry.forms
    assert entry.status == "verified"


# --- explain ----------------------------------------------------------------


def test_a_known_term_is_never_defined_again() -> None:
    item = _debate("Eine Aktuelle Stunde zur Bahn.")
    search = Search()
    llm = GlossaryLLM([("Aktuelle Stunde", "Aktuelle Stunde")])
    known = _entry("Aktuelle Stunde", definition="Geprüft.")
    _, entries, glossary = _run(llm, [item], {"aktuelle-stunde": known}, search=search)
    assert search.searched == []
    assert TermDefinitionBatch not in llm.calls
    assert glossary["aktuelle-stunde"].definition == "Geprüft."
    assert entries == []


def test_a_rejected_definition_is_not_shown_and_retried_a_few_times() -> None:
    item = _debate("Die Beschlussempfehlung des Ausschusses.")
    llm = GlossaryLLM(
        [("Beschlussempfehlung", "Beschlussempfehlung")],
        reject=("Beschlussempfehlung",),
    )
    _, _, glossary = _run(llm, [item])
    entry = glossary["beschlussempfehlung"]
    assert (entry.status, entry.definition, entry.attempts) == ("failed", None, 1)
    assert entry.sources == []
    # The ref stays on the item; the web shows only verified entries.
    assert [r.term_id for r in item.content["de"].terms] == ["beschlussempfehlung"]
    for _ in range(MAX_DEFINITION_ATTEMPTS):
        _run(llm, [], glossary)
    assert glossary["beschlussempfehlung"].attempts == MAX_DEFINITION_ATTEMPTS


def test_a_term_no_official_page_explains_is_not_shown() -> None:
    item = _debate("Die Beschlussempfehlung des Ausschusses.")
    llm = GlossaryLLM([("Beschlussempfehlung", "Beschlussempfehlung")])
    search = Search(nothing_for=("Beschlussempfehlung",))
    _, _, glossary = _run(llm, [item], search=search)
    entry = glossary["beschlussempfehlung"]
    assert (entry.status, entry.attempts) == ("failed", 1)
    assert TermDefinitionBatch not in llm.calls


def test_a_definition_citing_no_source_is_rejected() -> None:
    item = _debate("Die Beschlussempfehlung des Ausschusses.")
    llm = GlossaryLLM(
        [("Beschlussempfehlung", "Beschlussempfehlung")],
        cite_nothing=("Beschlussempfehlung",),
    )
    _, _, glossary = _run(llm, [item])
    entry = glossary["beschlussempfehlung"]
    assert (entry.status, entry.definition) == ("failed", None)


def test_a_definition_the_check_leaves_out_stays_pending() -> None:
    item = _debate("Die Beschlussempfehlung des Ausschusses.")
    llm = GlossaryLLM(
        [("Beschlussempfehlung", "Beschlussempfehlung")],
        omit=((DefinitionCheckBatch, "Beschlussempfehlung"),),
    )
    _, _, glossary = _run(llm, [item])
    entry = glossary["beschlussempfehlung"]
    assert (entry.status, entry.attempts, entry.definition) == ("pending", 0, None)


def test_a_definition_the_draft_leaves_out_stays_pending() -> None:
    item = _debate("Die Beschlussempfehlung des Ausschusses.")
    llm = GlossaryLLM(
        [("Beschlussempfehlung", "Beschlussempfehlung")],
        omit=((TermDefinitionBatch, "Beschlussempfehlung"),),
    )
    _, _, glossary = _run(llm, [item])
    assert (
        glossary["beschlussempfehlung"].status,
        glossary["beschlussempfehlung"].attempts,
    ) == (
        "pending",
        0,
    )


def test_a_failed_definition_call_keeps_the_term_pending() -> None:
    item = _debate("In einer Aktuellen Stunde ging es um die Bahn.")
    llm = GlossaryLLM(
        [("Aktuellen Stunde", "Aktuelle Stunde")], fail=(TermDefinitionBatch,)
    )
    _, _, glossary = _run(llm, [item])
    entry = glossary["aktuelle-stunde"]
    assert (entry.status, entry.attempts) == ("pending", 0)


def test_a_failed_search_or_an_unreadable_source_keeps_the_term_pending() -> None:
    for search, fetch in ((Search(fail=True), _fetch), (Search(), _unreachable)):
        item = _debate("In einer Aktuellen Stunde ging es um die Bahn.")
        llm = GlossaryLLM([("Aktuellen Stunde", "Aktuelle Stunde")])
        _, _, glossary = _run(llm, [item], search=search, fetch=fetch)
        entry = glossary["aktuelle-stunde"]
        assert (entry.status, entry.attempts) == ("pending", 0)
        assert TermDefinitionBatch not in llm.calls


def test_a_hand_written_entry_is_checked_against_its_sources_never_rewritten() -> None:
    hand = _entry(
        "Aktuelle Stunde",
        definition="Von Hand.",
        status="pending",
        generated_by="hand",
        prompt_version=None,
        attempts=0,
    )
    search = Search()
    llm = GlossaryLLM([])
    _, entries, glossary = _run(llm, [], {"aktuelle-stunde": hand}, search=search)
    assert search.searched == []
    assert TermDefinitionBatch not in llm.calls
    entry = glossary["aktuelle-stunde"]
    assert (entry.status, entry.definition) == ("verified", "Von Hand.")
    assert entries == [entry]


def test_a_hand_written_entry_its_sources_do_not_bear_out_is_hidden() -> None:
    for fields in (
        {"definition": "Von Hand."},
        {"definition": "Von Hand.", "sources": []},
    ):
        hand = _entry(
            "Aktuelle Stunde",
            status="pending",
            generated_by="hand",
            prompt_version=None,
            **fields,
        )
        llm = GlossaryLLM([], reject=("Aktuelle Stunde",))
        _, _, glossary = _run(llm, [], {"aktuelle-stunde": hand})
        entry = glossary["aktuelle-stunde"]
        assert (entry.status, entry.definition) == ("failed", "Von Hand.")


def test_a_new_prompt_version_checks_stored_entries_and_forms_again() -> None:
    stale = _entry(
        "Petitionsausschuss",
        forms=["Petitionsausschuss", "Petitionsausschusses", "Ausschuss"],
        prompt_version="1",
    )
    gave_up = _entry(
        "Beschlussempfehlung",
        definition=None,
        sources=[],
        status="failed",
        attempts=MAX_DEFINITION_ATTEMPTS,
        prompt_version="1",
    )
    search = Search()
    llm = GlossaryLLM([], reject_forms=("Ausschuss",))
    _, _, glossary = _run(
        llm,
        [],
        {"petitionsausschuss": stale, "beschlussempfehlung": gave_up},
        search=search,
    )
    assert glossary["petitionsausschuss"].forms == [
        "Petitionsausschuss",
        "Petitionsausschusses",
    ]
    assert sorted(search.searched) == ["Beschlussempfehlung", "Petitionsausschuss"]
    assert glossary["petitionsausschuss"].prompt_version == GLOSSARY_PROMPT_VERSION
    # A new version gives a term given up on its attempts back.
    assert glossary["beschlussempfehlung"].status == "verified"
    assert glossary["beschlussempfehlung"].attempts == 1


# --- ids and seed -----------------------------------------------------------


def test_term_ids_spell_out_umlauts() -> None:
    assert (
        term_id("Parlamentarischer Staatssekretär")
        == "parlamentarischer-staatssekretaer"
    )
    assert term_id("Ältestenrat") == "aeltestenrat"


def test_the_hand_written_seed_matches_what_the_job_reads() -> None:
    import json
    from pathlib import Path

    from ingestion.feed.glossary_sources import is_allowed

    seed = Path(__file__).resolve().parents[3] / "firebase" / "firestore_data"
    source = (seed.parent / "scripts" / "seed_firestore.py").read_text()
    start, end = source.index("def glossary_term_id"), source.index("def seed_glossary")
    namespace: dict[str, Any] = {}
    exec(source[start:end], namespace)  # noqa: S102 — our own seed script
    for row in json.loads((seed / "glossary.json").read_text(encoding="utf-8")):
        assert namespace["glossary_term_id"](row["term"]) == term_id(row["term"])
        assert row["term"] in row["forms"]
        assert len(row["definition"].split()) <= 35, row["term"]
        # Shown only with a source the job can check it against.
        sources = [GlossarySource.model_validate(s) for s in row["sources"]]
        assert sources and all(is_allowed(s.url) for s in sources), row["term"]

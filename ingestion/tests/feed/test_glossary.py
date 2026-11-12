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
from ingestion.feed.models import FeedItem
from ingestion.feed.prompts import (
    DefinitionCheck,
    DefinitionCheckBatch,
    ItemTerms,
    TermDefinition,
    TermDefinitionBatch,
    TermDraft,
    TermExtractionBatch,
)
from tests.feed.samples import sample_items

NOW = datetime(2026, 11, 12, 8, tzinfo=timezone.utc)
_REF_RE = re.compile(r"^\[([TB]\d+)\]", re.MULTILINE)


class GlossaryLLM:
    """Names the terms it is given for every text, defines each, and passes
    every definition but those it is told to reject."""

    def __init__(
        self,
        terms: list[tuple[str, str]],
        *,
        reject: tuple[str, ...] = (),
        fail: tuple[type, ...] = (),
    ) -> None:
        self.terms = terms
        self.reject = reject
        self.fail = fail
        self.calls: list[type] = []
        self.defined: list[str] = []

    async def __call__(self, messages: list, schema: type) -> tuple[Any, str]:
        self.calls.append(schema)
        if schema in self.fail:
            raise RuntimeError("quota")
        prompt = messages[0].content
        refs = _REF_RE.findall(prompt)
        if schema is TermExtractionBatch:
            return TermExtractionBatch(
                items=[
                    ItemTerms(
                        ref=ref,
                        terms=[TermDraft(surface=s, term=t) for s, t in self.terms],
                    )
                    for ref in refs
                ]
            ), "fake-model"
        if schema is TermDefinitionBatch:
            terms = re.findall(r"^\[B\d+\] (.+)$", prompt, re.MULTILINE)
            self.defined += terms
            return TermDefinitionBatch(
                definitions=[
                    TermDefinition(ref=ref, definition=f"{term} erklärt.")
                    for ref, term in zip(refs, terms)
                ]
            ), "fake-model"
        if schema is DefinitionCheckBatch:
            lines = re.findall(r"^\[(B\d+)\] (.+?):", prompt, re.MULTILINE)
            return DefinitionCheckBatch(
                checks=[
                    DefinitionCheck(ref=ref, reason="-", ok=term not in self.reject)
                    for ref, term in lines
                ]
            ), "fake-model"
        raise AssertionError(f"unexpected schema {schema}")


def _debate(teaser: str) -> FeedItem:
    item = next(i for i in sample_items() if i.debate is not None)
    item.content["de"].teaser = teaser
    return item


def _run(
    llm: GlossaryLLM,
    items: list[FeedItem],
    glossary: Optional[dict[str, GlossaryEntry]] = None,
) -> tuple[list[FeedItem], list[GlossaryEntry], dict[str, GlossaryEntry]]:
    glossary = {} if glossary is None else glossary
    builder = FeedBuilder(llm)
    try:
        changed, entries, _ = annotate_terms(items, builder, glossary, now=NOW)
    finally:
        builder.close()
    return changed, entries, glossary


def test_terms_are_found_defined_checked_and_stored() -> None:
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
    assert glossary["aktuelle-stunde"] is entry


def test_a_term_not_in_the_text_is_dropped() -> None:
    item = _debate("Der Bundestag beriet über die Bahn.")
    llm = GlossaryLLM([("Aktuellen Stunde", "Aktuelle Stunde")])
    _, entries, _ = _run(llm, [item])
    assert item.content["de"].terms == []
    assert entries == []
    # Looked at, so not asked about again until the text changes.
    assert not needs_terms(item)


def test_a_known_term_is_never_defined_again() -> None:
    known = GlossaryEntry(
        term_id="aktuelle-stunde",
        term="Aktuelle Stunde",
        definition="Von Hand.",
        forms=["Aktuelle Stunde"],
        status="verified",
        generated_by="hand",
        updated_at=NOW,
    )
    item = _debate("Eine Aktuelle Stunde zur Bahn.")
    llm = GlossaryLLM([("Aktuelle Stunde", "Aktuelle Stunde")])
    _, entries, glossary = _run(llm, [item], {"aktuelle-stunde": known})
    assert TermDefinitionBatch not in llm.calls
    assert glossary["aktuelle-stunde"].definition == "Von Hand."
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
    # The ref stays on the item; the web shows only verified entries.
    assert [r.term_id for r in item.content["de"].terms] == ["beschlussempfehlung"]
    for _ in range(MAX_DEFINITION_ATTEMPTS):
        _run(llm, [], glossary)
    assert glossary["beschlussempfehlung"].attempts == MAX_DEFINITION_ATTEMPTS


def test_a_failed_call_leaves_the_item_for_the_next_run() -> None:
    item = _debate("In einer Aktuellen Stunde ging es um die Bahn.")
    llm = GlossaryLLM(
        [("Aktuellen Stunde", "Aktuelle Stunde")], fail=(TermExtractionBatch,)
    )
    changed, entries, _ = _run(llm, [item])
    assert (changed, entries) == ([], [])
    assert needs_terms(item)


def test_a_failed_definition_call_keeps_the_term_pending() -> None:
    item = _debate("In einer Aktuellen Stunde ging es um die Bahn.")
    llm = GlossaryLLM(
        [("Aktuellen Stunde", "Aktuelle Stunde")], fail=(TermDefinitionBatch,)
    )
    _, _, glossary = _run(llm, [item])
    entry = glossary["aktuelle-stunde"]
    assert (entry.status, entry.attempts) == ("pending", 0)


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


def test_term_ids_spell_out_umlauts() -> None:
    assert (
        term_id("Parlamentarischer Staatssekretär")
        == "parlamentarischer-staatssekretaer"
    )
    assert term_id("Ältestenrat") == "aeltestenrat"


def test_the_hand_written_seed_matches_what_the_job_reads() -> None:
    import json
    from pathlib import Path

    seed = Path(__file__).resolve().parents[3] / "firebase" / "firestore_data"
    source = (seed.parent / "scripts" / "seed_firestore.py").read_text()
    start, end = source.index("def glossary_term_id"), source.index("def seed_glossary")
    namespace: dict[str, Any] = {}
    exec(source[start:end], namespace)  # noqa: S102 — our own seed script
    for row in json.loads((seed / "glossary.json").read_text(encoding="utf-8")):
        assert namespace["glossary_term_id"](row["term"]) == term_id(row["term"])
        assert row["term"] in row["forms"]
        assert len(row["definition"].split()) <= 35, row["term"]

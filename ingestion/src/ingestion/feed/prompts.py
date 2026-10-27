# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Prompts and structured-output schemas for the feed's LLM steps.

Every prompt draws its editorial rules from the constants below, so the
generation and the translation of a text are held to the same standard of
neutrality, grounding and attribution.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from ingestion.feed.topics import DigestTopic, topic_legend

# Part of every digest's input_hash: bumping it regenerates all stored days.
PROMPT_VERSION = "7"
# Stored on each translation: bumping it re-translates, never regenerates.
TRANSLATION_PROMPT_VERSION = "1"

# The shared rulebook.
_AUDIENCE = "eine tägliche, neutrale Übersicht"
_NEUTRALITY_RULE = "Keine Wertung, keine Empfehlung, keine Spekulation über Motive."
_GROUNDING_RULE = "Erfinde nichts, was nicht in den Auszügen steht."
_ATTRIBUTION_RULE = (
    "Neutral bleiben: Positionen den Fraktionen zuschreiben, nicht bewerten."
)
_POSITION_SENTENCE_RULE = (
    "Der Positionssatz steht direkt hinter dem Parteinamen: ohne Subjekt, mit "
    'dem Verb im Plural ("Wenden sich gegen …", "Fordern …", "Begrüßen …"), nicht '
    '"Die Fraktion kritisierte …".'
)
_QUESTION_STYLE = (
    "kurze Fragen (höchstens 8 Wörter) aus Sicht einer Bürgerin, "
    "die man dazu stellen würde"
)


# Votes and debates are tagged alike, so both land under the same filters.
_TOPICS_DESCRIPTION = "1 bis 2 Themen-Schlüssel, das wichtigste zuerst."
_TOPIC_KEYS_RULE = "(nur die Schlüssel verwenden; 'other' nur, wenn nichts passt)"


def _refs_only_rule(examples: str, field: str, elsewhere: str) -> str:
    return f"Die Kennungen ({examples}) gehören NUR in {field}, nie in {elsewhere}."


_QUESTIONS_DESCRIPTION = f"Genau 3 {_QUESTION_STYLE}, z. B. 'Was heißt das für mich?'."


class VoteEnrichment(BaseModel):
    ref: str = Field(description="Die Kennung der Abstimmung, z. B. 'V3'.")
    topics: list[DigestTopic] = Field(description=_TOPICS_DESCRIPTION)
    short_title: str = Field(
        description="Verständlicher Titel, höchstens 12 Wörter, ohne Drucksachennummern."
    )
    summary: str = Field(
        description="Höchstens 2 neutrale Sätze: worüber wurde abgestimmt und was ändert sich."
    )
    suggested_questions: list[str] = Field(
        default_factory=list, description=_QUESTIONS_DESCRIPTION
    )


class VoteEnrichmentBatch(BaseModel):
    votes: list[VoteEnrichment]


class PartyPositionDraft(BaseModel):
    party_id: str = Field(
        description="Partei-Kennung genau wie in den Auszügen in Klammern, z. B. 'spd'."
    )
    speakers: list[str] = Field(
        description="Namen der Redner:innen dieser Fraktion, genau wie in den Auszügen."
    )
    position: str = Field(
        description=(
            "Ein neutraler Satz zur Position der Fraktion, ohne Subjekt und mit "
            "dem Verb im Plural, z. B. 'Wenden sich gegen Einsparungen bei …'."
        )
    )


class OpeningQuoteDraft(BaseModel):
    speaker: str = Field(
        description="Nur der Name der ersten Redner:in, ohne Partei, genau wie in den Auszügen."
    )
    quote: str = Field(
        description="Ein kurzer, wörtlich übernommener Kernsatz (höchstens 25 Wörter) aus dieser ersten Rede, unverändert."
    )


class SessionSectionDraft(BaseModel):
    topics: list[DigestTopic] = Field(description=_TOPICS_DESCRIPTION)
    headline: str = Field(description="Kurze Überschrift, höchstens 10 Wörter.")
    summary: str = Field(
        description="1 bis 2 neutrale Sätze: worum ging es in der Debatte."
    )
    positions: list[PartyPositionDraft] = Field(
        default_factory=list,
        description="Je Fraktion, die zu diesem Thema gesprochen hat, ein Eintrag.",
    )
    agenda_refs: list[str] = Field(
        description="Kennungen der zugrunde liegenden Tagesordnungspunkte, z. B. ['A2', 'A5']."
    )
    key_points: list[str] = Field(
        default_factory=list,
        description=(
            "Genau 3 Stichpunkte, je ein kurzer Satz: was vorgelegt wurde, "
            "worüber am meisten gestritten wurde, wie es weitergeht."
        ),
    )
    heat: Optional[int] = Field(
        None,
        description=(
            "Hitzigkeit 1 bis 5 IM VERGLEICH zu den anderen Abschnitten dieser "
            "Sitzung: der hitzigste Abschnitt bekommt 5."
        ),
    )
    opening_quote: Optional[OpeningQuoteDraft] = None
    suggested_questions: list[str] = Field(
        default_factory=list, description=_QUESTIONS_DESCRIPTION
    )


class SessionSummaryDraft(BaseModel):
    sections: list[SessionSectionDraft]
    other_topics: list[str] = Field(
        description="Kurze Stichworte für kleinere Tagesordnungspunkte ohne eigenen Abschnitt."
    )


class TranslatedSegment(BaseModel):
    ref: str = Field(description="Die Kennung des Abschnitts, z. B. 'S3'.")
    text: str = Field(description="Der Abschnitt auf Englisch, und nur dieser.")


class TranslationBatch(BaseModel):
    segments: list[TranslatedSegment]


VOTE_ENRICHMENT_PROMPT = f"""\
Du bereitest Abstimmungen aus dem {{parliament}} für {_AUDIENCE} \
für Bürgerinnen und Bürger auf.

Ordne jeder Abstimmung 1 bis 2 Themen aus dieser Liste zu {_TOPIC_KEYS_RULE}:
{{topics}}

Formuliere außerdem einen verständlichen Kurztitel, höchstens zwei neutrale \
Sätze, worum es geht, und drei kurze Fragen, die Bürgerinnen und Bürger dazu \
stellen würden. {_NEUTRALITY_RULE} \
Gib für JEDE Abstimmung genau einen Eintrag mit ihrer Kennung zurück.

Abstimmungen:
{{votes}}
"""

SESSION_SUMMARY_PROMPT = f"""\
Du fasst die Plenarsitzung des {{parliament}} vom {{day}} für {_AUDIENCE} \
zusammen. Grundlage sind ausschließlich die folgenden \
Redeauszüge, gruppiert nach Tagesordnungspunkten.

Gliedere die Zusammenfassung nach Themen aus dieser Liste {_TOPIC_KEYS_RULE}:
{{topics}}

Regeln:
- Ein Abschnitt pro Hauptthema; fasse Tagesordnungspunkte zum selben \
Hauptthema zusammen.
- topics: 1 bis 2 Themen je Abschnitt, das Hauptthema zuerst; ein zweites \
nur, wenn die Debatte es wesentlich berührt.
- Höchstens 6 Abschnitte, die wichtigsten Debatten zuerst.
- Jeder Abschnitt nennt in agenda_refs die Kennungen der Tagesordnungspunkte, \
auf denen er beruht. {_GROUNDING_RULE}
- {_ATTRIBUTION_RULE}
- In summary nur, worum es ging. Die Positionen gehören in positions: für \
jede Fraktion, die zu dem Thema gesprochen hat, ein Eintrag mit ihren \
Redner:innen und einem Satz zu ihrer Position. Partei-Kennungen und Namen \
exakt so übernehmen, wie sie in den Auszügen stehen.
- {_POSITION_SENTENCE_RULE}
- key_points: genau drei kurze Sätze (was vorgelegt wurde, worüber am meisten \
gestritten wurde, wie es weitergeht).
- heat: vergleiche die Abschnitte DIESER Sitzung miteinander (Zwischenrufe, \
Schärfe, gegensätzliche Positionen). Der hitzigste bekommt 5, die anderen \
entsprechend weniger. Keine absolute Skala.
- opening_quote: ein kurzer wörtlicher Satz (höchstens 25 Wörter) aus der \
ersten Rede des Abschnitts, Zeichen für Zeichen aus dem Auszug kopiert; als \
speaker nur den Namen, ohne die Partei in Klammern.
- suggested_questions: drei kurze Fragen aus Sicht von Bürgerinnen und Bürgern.
- Kleinere Punkte ohne eigenen Abschnitt als kurze Stichworte in other_topics.
- {_refs_only_rule("A1, A2, …", "agenda_refs", "Überschriften, Zusammenfassungen oder other_topics")}

Tagesordnungspunkte:
{{agenda}}
"""

# Segment by segment, not field by field inside one JSON object: asked to
# translate a whole entry, the model runs past the end of a paragraph into
# the footers of web translation tools and never closes the JSON string.
TRANSLATION_PROMPT = f"""\
Du übersetzt Einträge aus dem {{parliament}} für {_AUDIENCE} \
für Bürgerinnen und Bürger ins Englische. Grundlage sind ausschließlich die \
folgenden deutschen Auszüge; sie sind bereits geprüft und veröffentlicht. \
Jeder Auszug ist in nummerierte Abschnitte geteilt: Überschrift, \
Zusammenfassung, Stichpunkte, Positionssätze der Fraktionen, Fragen und \
wörtliche Zitate.

Regeln:
- Übersetze treu: nichts hinzufügen, nichts weglassen, nichts abschwächen \
oder zuspitzen. {_GROUNDING_RULE}
- {_NEUTRALITY_RULE}
- {_ATTRIBUTION_RULE}
- {_POSITION_SENTENCE_RULE} Im Englischen ebenso: "Oppose …", "Call for …", \
"Welcome …", nicht "The parliamentary group criticised …".
- Zahlen, Namen, Partei-Kennungen, Drucksachen- und Protokollnummern \
unverändert übernehmen.
- Eigennamen deutscher Institutionen und Gesetze (z. B. Bundestag, \
Bundesrat) dürfen deutsch bleiben, wenn es keine übliche englische \
Bezeichnung gibt.
- Wörtliche Zitate (in „…“) sinngetreu übersetzen, nicht umschreiben oder \
kürzen.
- Jeder Abschnitt wird für sich übersetzt: genau ein Eintrag je Abschnitt, \
mit seiner Kennung, und nur der übersetzte Abschnitt, ohne Anmerkungen.
- {_refs_only_rule("S1, S2, …", "ref", "den übersetzten Texten")}

Abschnitte:
{{segments}}
"""


def format_vote_prompt(parliament: str, votes_block: str) -> str:
    return VOTE_ENRICHMENT_PROMPT.format(
        parliament=parliament, topics=topic_legend(), votes=votes_block
    )


def format_session_prompt(parliament: str, day: str, agenda_block: str) -> str:
    return SESSION_SUMMARY_PROMPT.format(
        parliament=parliament, day=day, topics=topic_legend(), agenda=agenda_block
    )


def format_translation_prompt(parliament: str, segments_block: str) -> str:
    return TRANSLATION_PROMPT.format(parliament=parliament, segments=segments_block)

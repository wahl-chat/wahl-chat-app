# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Prompts and structured-output schemas for the feed's LLM steps.

The prompts say what to do, why and by which editorial rules; the schema
field descriptions say what each field must hold. Every prompt draws its
rules from the constants below, so the generation and the translation of a
text are held to the same standard of neutrality, grounding and attribution.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from ingestion.feed.topics import DigestTopic, topic_legend

# Recorded on the German texts an item is generated with. A change does not
# regenerate stored items: rebuild a chosen window with --force after the eval.
PROMPT_VERSION = "12"
# Stored on each translation: bumping it re-translates, never regenerates.
TRANSLATION_PROMPT_VERSION = "1"
# Part of each item's terms hash: bumping it looks for terms again. Stored on
# each glossary definition.
GLOSSARY_PROMPT_VERSION = "1"

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
# The model sees the topics as "- key: label" lines; it answers with the key.
_TOPICS_DESCRIPTION = (
    "1 bis 2 Themen als Kennung aus der Themenliste (das Wort vor dem "
    "Doppelpunkt), das wichtigste zuerst. Ein zweites nur, wenn es wesentlich "
    "berührt wird; 'other' nur, wenn nichts passt."
)


def _refs_only_rule(examples: str, field: str, elsewhere: str) -> str:
    return f"Die Kennungen ({examples}) gehören NUR in {field}, nie in {elsewhere}."


# Every bullet and position names the speeches it draws on, so the reader can
# open the very passage; the code finds the passage, the model only the speech.
_SOURCES_DESCRIPTION = (
    "Die Kennungen der ein bis zwei Reden, die sagen, was der Satz aussagt, "
    "z. B. ['R3']. Bei einem Positionssatz nur Reden seiner Fraktion."
)
_SOURCES_RULE = (
    "Jeder Stichpunkt und jeder Positionssatz stützt sich auf die Reden, die "
    "er in sources nennt; ein Positionssatz nur auf Reden SEINER Fraktion. "
    + _refs_only_rule("R1, R2, …", "sources", "die Texte")
)

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
        description="Partei-Kennung genau wie in der Liste der Fraktionen, z. B. 'spd'."
    )
    position: str = Field(
        description="Ein neutraler Satz zur Position der Fraktion. "
        + _POSITION_SENTENCE_RULE
    )
    sources: list[str] = Field(default_factory=list, description=_SOURCES_DESCRIPTION)


# Every card is a debate, so a headline that says so carries no information
# and makes the feed read the same card after card.
_DEBATE_HEADLINE_DESCRIPTION = (
    "Kurze Überschrift, höchstens 10 Wörter. Nennt direkt den Inhalt oder "
    "Streitpunkt. Nicht mit „Debatte über/zu“, „Bundestag debattiert“ oder "
    "ähnlichen Formeln beginnen. Gut: „Mehr Geld für Kitas: Streit um die "
    "Finanzierung“. Schlecht: „Debatte über die Kita-Finanzierung“."
)


class KeyPointDraft(BaseModel):
    text: str = Field(description="Ein kurzer Satz, ohne Kennungen wie R3.")
    sources: list[str] = Field(default_factory=list, description=_SOURCES_DESCRIPTION)


class OpeningQuoteDraft(BaseModel):
    speaker: str = Field(
        description="Nur der Name der ersten Redner:in, ohne Partei, genau wie in den Reden."
    )
    quote: str = Field(
        description=(
            "Ein kurzer Kernsatz (höchstens 25 Wörter) aus der ersten Rede, "
            "Zeichen für Zeichen kopiert."
        )
    )


class DebateDraft(BaseModel):
    topics: list[DigestTopic] = Field(description=_TOPICS_DESCRIPTION)
    headline: str = Field(description=_DEBATE_HEADLINE_DESCRIPTION)
    summary: str = Field(
        description=(
            "1 bis 2 neutrale Sätze: worum ging es in der Debatte. Nur das "
            "Thema; die Positionen gehören in positions."
        )
    )
    positions: list[PartyPositionDraft] = Field(
        default_factory=list,
        description=(
            "Genau ein Eintrag für jede Fraktion aus der Liste der Fraktionen, "
            "keine andere."
        ),
    )
    key_points: list[KeyPointDraft] = Field(
        default_factory=list,
        description=(
            "Genau 3 Stichpunkte, je ein kurzer Satz: was vorgelegt wurde, "
            "worüber am meisten gestritten wurde, wie es weitergeht."
        ),
    )
    opening_quote: Optional[OpeningQuoteDraft] = Field(
        default=None, description="Ein wörtlicher Satz aus der ersten Rede."
    )
    suggested_questions: list[str] = Field(
        default_factory=list, description=_QUESTIONS_DESCRIPTION
    )


class PositionsDraft(BaseModel):
    positions: list[PartyPositionDraft] = Field(
        description=(
            "Genau ein Eintrag für jede Fraktion aus der Liste der Fraktionen, "
            "keine andere."
        )
    )


# The reason comes before the verdict, so the model reasons before it decides.
class PositionCheck(BaseModel):
    ref: str = Field(description="Die Kennung des Positionssatzes, z. B. 'P2'.")
    reason: str = Field(
        description=(
            "Zuerst, in einem kurzen Satz: was sagen die Reden dieser Fraktion, "
            "und weicht der Satz davon ab?"
        )
    )
    supported: bool = Field(
        description=(
            "true nur, wenn der Satz nichts enthält, was die Reden dieser "
            "Fraktion nicht sagen, nichts zuspitzt oder abschwächt und keine "
            "Forderung erfindet. Im Zweifel false."
        )
    )


class PositionCheckBatch(BaseModel):
    checks: list[PositionCheck]


class TranslatedSegment(BaseModel):
    ref: str = Field(description="Die Kennung des Abschnitts, z. B. 'S3'.")
    text: str = Field(description="Der Abschnitt auf Englisch, und nur dieser.")


class TranslationBatch(BaseModel):
    segments: list[TranslatedSegment]


VOTE_ENRICHMENT_PROMPT = f"""\
Du bereitest Abstimmungen aus dem {{parliament}} für {_AUDIENCE} \
für Bürgerinnen und Bürger auf. Wer den Eintrag liest, soll ohne Fachwissen \
verstehen, worüber abgestimmt wurde.

Themenliste:
{{topics}}

Regeln:
- {_GROUNDING_RULE}
- {_NEUTRALITY_RULE}
- Gib für JEDE Abstimmung genau einen Eintrag mit ihrer Kennung zurück.

Abstimmungen:
{{votes}}
"""

_POSITION_FIDELITY_RULE = (
    "Jeder Positionssatz gibt nur wieder, was die Redner:innen dieser Fraktion "
    "in DIESER Debatte gesagt haben: nichts zuspitzen, nichts abschwächen, "
    "keine Forderung erfinden (wer eine Prüfung verlangt, fordert keine "
    "Abschaffung)."
)

DEBATE_PROMPT = f"""\
Du fasst eine Debatte aus dem {{parliament}} vom {{day}} für {_AUDIENCE} \
zusammen. Grundlage sind ausschließlich die folgenden Reden zum \
Tagesordnungspunkt „{{agenda}}“, in der Reihenfolge, in der sie gehalten \
wurden. Wer die Zusammenfassung liest, soll verstehen, worum es ging und wo \
jede Fraktion steht, ohne die Reden zu lesen.

Fraktionen, die gesprochen haben: {{parties}}

Themenliste:
{{topics}}

Regeln:
- {_GROUNDING_RULE}
- {_NEUTRALITY_RULE}
- {_ATTRIBUTION_RULE}
- {_POSITION_FIDELITY_RULE}
- {_SOURCES_RULE}

Reden:
{{speeches}}
"""

POSITIONS_PROMPT = f"""\
Du fasst für {_AUDIENCE} zusammen, welche Position einzelne Fraktionen in \
einer Debatte aus dem {{parliament}} zum Tagesordnungspunkt „{{agenda}}“ \
vertreten haben. Grundlage sind ausschließlich die Reden unten.

Fraktionen: {{parties}}

Regeln:
- {_GROUNDING_RULE}
- {_NEUTRALITY_RULE}
- {_ATTRIBUTION_RULE}
- {_POSITION_FIDELITY_RULE}
- {_SOURCES_RULE}

Reden:
{{speeches}}
"""

VERIFY_PROMPT = f"""\
Du prüfst Positionssätze für {_AUDIENCE}, bevor sie unter dem Namen einer \
Fraktion veröffentlicht werden. Eine falsch zugeschriebene Position ist der \
schwerste Fehler, den diese Übersicht machen kann.

Prüfe jeden Satz einzeln gegen die Reden SEINER Fraktion zum \
Tagesordnungspunkt „{{agenda}}“ im {{parliament}}.
Gib für JEDEN Satz genau einen Eintrag mit seiner Kennung zurück.

Positionssätze:
{{positions}}

Reden je Fraktion:
{{speeches}}
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


def format_debate_prompt(
    parliament: str, day: str, agenda: str, parties: str, speeches: str
) -> str:
    return DEBATE_PROMPT.format(
        parliament=parliament,
        day=day,
        agenda=agenda,
        topics=topic_legend(),
        parties=parties,
        speeches=speeches,
    )


def format_positions_prompt(
    parliament: str, agenda: str, parties: str, speeches: str
) -> str:
    return POSITIONS_PROMPT.format(
        parliament=parliament, agenda=agenda, parties=parties, speeches=speeches
    )


def format_verify_prompt(
    parliament: str, agenda: str, positions: str, speeches: str
) -> str:
    return VERIFY_PROMPT.format(
        parliament=parliament, agenda=agenda, positions=positions, speeches=speeches
    )


def format_translation_prompt(parliament: str, segments_block: str) -> str:
    return TRANSLATION_PROMPT.format(parliament=parliament, segments=segments_block)


# --- glossary ---------------------------------------------------------------


class TermDraft(BaseModel):
    surface: str = Field(
        description="Der Begriff genau so, wie er im Text steht, Zeichen für Zeichen."
    )
    term: str = Field(
        description=(
            "Die Grundform im Nominativ Singular, z. B. „Aktuelle Stunde“ für "
            "„Aktuellen Stunde“, „Parlamentarischer Staatssekretär“ für "
            "„Parlamentarische Staatssekretärin“."
        )
    )


class ItemTerms(BaseModel):
    ref: str = Field(description="Die Kennung des Textes, z. B. 'T2'.")
    terms: list[TermDraft] = Field(
        default_factory=list,
        description="Höchstens 4 Fachbegriffe; leer, wenn keiner vorkommt.",
    )


class TermExtractionBatch(BaseModel):
    items: list[ItemTerms]


class TermDefinition(BaseModel):
    ref: str = Field(description="Die Kennung des Begriffs, z. B. 'B3'.")
    definition: str = Field(
        description=(
            "1 bis 2 Sätze, höchstens 35 Wörter, in einfacher Sprache: was der "
            "Begriff im parlamentarischen Alltag bedeutet."
        )
    )


class TermDefinitionBatch(BaseModel):
    definitions: list[TermDefinition]


# The reason comes before the verdict, so the model reasons before it decides.
class DefinitionCheck(BaseModel):
    ref: str = Field(description="Die Kennung des Begriffs, z. B. 'B3'.")
    reason: str = Field(
        description="Zuerst, in einem kurzen Satz: stimmt die Erklärung, und ist sie neutral?"
    )
    ok: bool = Field(
        description=(
            "true nur, wenn die Erklärung sachlich richtig ist, nichts wertet, "
            "keine Partei und kein aktuelles Beispiel nennt und ohne Vorwissen "
            "verständlich ist. Im Zweifel false."
        )
    )


class DefinitionCheckBatch(BaseModel):
    checks: list[DefinitionCheck]


TERMS_PROMPT = f"""\
Leser:innen ohne politisches Vorwissen lesen {_AUDIENCE} über den \
{{parliament}}. Unten stehen kurze Texte daraus, jeder mit einer Kennung wie \
[T1]. Nenne für jeden Text die Fachbegriffe aus dem parlamentarischen \
Verfahren, dem Staatsaufbau oder der Verwaltung, die so jemand vermutlich \
nicht kennt: etwa Aktuelle Stunde, Regierungsbefragung, Beschlussempfehlung, \
Petitionsausschuss, Parlamentarische Staatssekretärin.

Regeln:
- Nur Begriffe, die wörtlich im Text stehen.
- Keine Partei- oder Personennamen, keine Alltagswörter und keine \
Themenwörter wie „Rente“ oder „Klimaschutz“.
- Gib jeden Text mit seiner Kennung zurück, auch wenn er keinen Begriff enthält.

Texte:
{{texts}}
"""

DEFINITION_PROMPT = f"""\
Erkläre die folgenden Fachbegriffe für {_AUDIENCE} über den {{parliament}}, \
für Leser:innen ohne politisches Vorwissen. Jeder Begriff hat eine Kennung \
wie [B1].

Regeln:
- Erkläre, was der Begriff im parlamentarischen Alltag bedeutet, nicht, wie \
er politisch zu bewerten ist.
- {_NEUTRALITY_RULE}
- Nenne keine Parteien, keine Personen und keine aktuellen Beispiele.
- Ist ein Begriff ein Amt, erkläre das Amt, nicht die Person.

Begriffe:
{{terms}}
"""

DEFINITION_CHECK_PROMPT = f"""\
Prüfe jede Erklärung eines Fachbegriffs aus dem {{parliament}}. Sie soll \
sachlich richtig, neutral und ohne Vorwissen verständlich sein. \
{_NEUTRALITY_RULE}

Erklärungen:
{{definitions}}
"""


def format_terms_prompt(parliament: str, texts_block: str) -> str:
    return TERMS_PROMPT.format(parliament=parliament, texts=texts_block)


def format_definition_prompt(parliament: str, terms_block: str) -> str:
    return DEFINITION_PROMPT.format(parliament=parliament, terms=terms_block)


def format_definition_check_prompt(parliament: str, definitions_block: str) -> str:
    return DEFINITION_CHECK_PROMPT.format(
        parliament=parliament, definitions=definitions_block
    )

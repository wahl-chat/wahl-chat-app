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

# Part of every item's input_hash: bumping it regenerates all stored items.
PROMPT_VERSION = "8"
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
# Absolute, so each debate is rated on its own; the page rescales against
# the hottest debate of the day it shows.
_HEAT_SCALE = (
    "1 = sachlich, kaum Widerspruch; 2 = unterschiedliche Positionen, ruhiger "
    "Ton; 3 = deutliche Gegensätze, spürbare Schärfe; 4 = scharfer Ton, "
    "gegenseitige Vorwürfe; 5 = außergewöhnlich hitzig, persönliche Angriffe "
    "oder Ordnungsrufe."
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
        description="Partei-Kennung genau wie in den Reden in Klammern, z. B. 'spd'."
    )
    position: str = Field(
        description=(
            "Ein neutraler Satz zur Position der Fraktion, ohne Subjekt und mit "
            "dem Verb im Plural, z. B. 'Wenden sich gegen Einsparungen bei …'."
        )
    )


class OpeningQuoteDraft(BaseModel):
    speaker: str = Field(
        description="Nur der Name der ersten Redner:in, ohne Partei, genau wie in den Reden."
    )
    quote: str = Field(
        description="Ein kurzer, wörtlich übernommener Kernsatz (höchstens 25 Wörter) aus der ersten Rede, unverändert."
    )


class DebateDraft(BaseModel):
    topics: list[DigestTopic] = Field(description=_TOPICS_DESCRIPTION)
    headline: str = Field(description="Kurze Überschrift, höchstens 10 Wörter.")
    summary: str = Field(
        description="1 bis 2 neutrale Sätze: worum ging es in der Debatte."
    )
    positions: list[PartyPositionDraft] = Field(
        default_factory=list,
        description="Genau ein Eintrag je Fraktion, die in der Debatte gesprochen hat.",
    )
    key_points: list[str] = Field(
        default_factory=list,
        description=(
            "Genau 3 Stichpunkte, je ein kurzer Satz: was vorgelegt wurde, "
            "worüber am meisten gestritten wurde, wie es weitergeht."
        ),
    )
    heat: Optional[int] = Field(
        None, description=f"Hitzigkeit auf einer festen Skala: {_HEAT_SCALE}"
    )
    opening_quote: Optional[OpeningQuoteDraft] = None
    suggested_questions: list[str] = Field(
        default_factory=list, description=_QUESTIONS_DESCRIPTION
    )


class PositionsDraft(BaseModel):
    positions: list[PartyPositionDraft]


class PositionCheck(BaseModel):
    ref: str = Field(description="Die Kennung des Positionssatzes, z. B. 'P2'.")
    supported: bool = Field(
        description="true nur, wenn die Reden dieser Fraktion den Satz vollständig stützen."
    )
    reason: str = Field(description="Ein kurzer Satz zur Begründung.")


class PositionCheckBatch(BaseModel):
    checks: list[PositionCheck]


class PositionAgreement(BaseModel):
    ref: str = Field(description="Die Kennung des Satzpaares, z. B. 'P2'.")
    agrees: bool = Field(
        description="true, wenn beide Sätze der Fraktion dieselbe Position zuschreiben."
    )
    reason: str = Field(description="Ein kurzer Satz zur Begründung.")


class PositionAgreementBatch(BaseModel):
    pairs: list[PositionAgreement]


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
wurden.

Ordne die Debatte 1 bis 2 Themen aus dieser Liste zu {_TOPIC_KEYS_RULE}:
{{topics}}

Regeln:
- topics: das Hauptthema zuerst; ein zweites nur, wenn die Debatte es \
wesentlich berührt.
- {_GROUNDING_RULE}
- {_NEUTRALITY_RULE}
- {_ATTRIBUTION_RULE}
- In summary nur, worum es ging. Die Positionen gehören in positions.
- positions: genau ein Eintrag für JEDE dieser Fraktionen, keine andere: \
{{parties}}. Partei-Kennungen exakt so übernehmen.
- {_POSITION_FIDELITY_RULE}
- {_POSITION_SENTENCE_RULE}
- key_points: genau drei kurze Sätze (was vorgelegt wurde, worüber am meisten \
gestritten wurde, wie es weitergeht).
- heat: wie hitzig die Debatte war, auf dieser festen Skala: {_HEAT_SCALE}
- opening_quote: ein kurzer wörtlicher Satz (höchstens 25 Wörter) aus der \
ersten Rede, Zeichen für Zeichen kopiert; als speaker nur den Namen, ohne die \
Partei in Klammern.
- suggested_questions: drei kurze Fragen aus Sicht von Bürgerinnen und Bürgern.

Reden:
{{speeches}}
"""

POSITIONS_PROMPT = f"""\
Du fasst für {_AUDIENCE} zusammen, welche Position einzelne Fraktionen in \
einer Debatte aus dem {{parliament}} zum Tagesordnungspunkt „{{agenda}}“ \
vertreten haben. Grundlage sind ausschließlich die Reden unten.

Regeln:
- Genau ein Eintrag für JEDE dieser Fraktionen, keine andere: {{parties}}. \
Partei-Kennungen exakt so übernehmen.
- {_GROUNDING_RULE}
- {_NEUTRALITY_RULE}
- {_ATTRIBUTION_RULE}
- {_POSITION_FIDELITY_RULE}
- {_POSITION_SENTENCE_RULE}

Reden:
{{speeches}}
"""

VERIFY_PROMPT = f"""\
Du prüfst Positionssätze für {_AUDIENCE}, bevor sie unter dem Namen einer \
Fraktion veröffentlicht werden. Eine falsch zugeschriebene Position ist der \
schwerste Fehler, den diese Übersicht machen kann.

Prüfe jeden Satz einzeln gegen die Reden SEINER Fraktion zum \
Tagesordnungspunkt „{{agenda}}“ im {{parliament}}. supported ist nur dann \
true, wenn der Satz nichts enthält, was diese Reden nicht sagen, nichts \
zuspitzt oder abschwächt und keine Forderung erfindet. Im Zweifel false.
Gib für JEDEN Satz genau einen Eintrag mit seiner Kennung zurück.

Positionssätze:
{{positions}}

Reden je Fraktion:
{{speeches}}
"""

# Used only by the evaluation against the gold set, never in a build.
AGREEMENT_PROMPT = """\
Du vergleichst je zwei Sätze, die einer Fraktion eine Position in einer \
Debatte zum Tagesordnungspunkt „{agenda}“ zuschreiben: A ist eine von Hand \
geprüfte Referenz, B ein zu prüfender Entwurf. agrees ist true, wenn B der \
Fraktion inhaltlich dieselbe Position zuschreibt wie A: andere Worte sind \
in Ordnung, eine andere, zugespitzte, abgeschwächte oder zusätzliche \
Forderung nicht.
Gib für JEDES Paar genau einen Eintrag mit seiner Kennung zurück.

Paare:
{pairs}
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


def format_agreement_prompt(agenda: str, pairs: str) -> str:
    return AGREEMENT_PROMPT.format(agenda=agenda, pairs=pairs)


def format_translation_prompt(parliament: str, segments_block: str) -> str:
    return TRANSLATION_PROMPT.format(parliament=parliament, segments=segments_block)

# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Prompts and structured-output schemas for the digest's two LLM steps."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.daily_digest.topics import DigestTopic, topic_legend

# Part of every digest's input_hash: bumping it regenerates all stored days.
PROMPT_VERSION = "4"


class VoteEnrichment(BaseModel):
    ref: str = Field(description="Die Kennung der Abstimmung, z. B. 'V3'.")
    topics: list[DigestTopic] = Field(
        description="1 bis 2 Themen-Schlüssel, das wichtigste zuerst."
    )
    short_title: str = Field(
        description="Verständlicher Titel, höchstens 12 Wörter, ohne Drucksachennummern."
    )
    summary: str = Field(
        description="Ein neutraler Satz: worüber wurde abgestimmt und was bedeutet es."
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


class SessionSectionDraft(BaseModel):
    topic: DigestTopic
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


class SessionSummaryDraft(BaseModel):
    sections: list[SessionSectionDraft]
    other_topics: list[str] = Field(
        description="Kurze Stichworte für kleinere Tagesordnungspunkte ohne eigenen Abschnitt."
    )


VOTE_ENRICHMENT_PROMPT = """\
Du bereitest Abstimmungen aus dem {parliament} für eine tägliche, neutrale \
Übersicht für Bürgerinnen und Bürger auf.

Ordne jeder Abstimmung 1 bis 2 Themen aus dieser Liste zu (nur die Schlüssel \
verwenden; 'other' nur, wenn nichts passt):
{topics}

Formuliere außerdem einen verständlichen Kurztitel und einen neutralen Satz, \
worum es geht. Keine Wertung, keine Empfehlung, keine Spekulation über Motive. \
Gib für JEDE Abstimmung genau einen Eintrag mit ihrer Kennung zurück.

Abstimmungen:
{votes}
"""

SESSION_SUMMARY_PROMPT = """\
Du fasst die Plenarsitzung des {parliament} vom {day} für eine tägliche, \
neutrale Übersicht zusammen. Grundlage sind ausschließlich die folgenden \
Redeauszüge, gruppiert nach Tagesordnungspunkten.

Gliedere die Zusammenfassung nach Themen aus dieser Liste (nur die Schlüssel \
verwenden):
{topics}

Regeln:
- Ein Abschnitt pro Thema; fasse Tagesordnungspunkte zum selben Thema zusammen.
- Höchstens 6 Abschnitte, die wichtigsten Debatten zuerst.
- Jeder Abschnitt nennt in agenda_refs die Kennungen der Tagesordnungspunkte, \
auf denen er beruht. Erfinde nichts, was nicht in den Auszügen steht.
- Neutral bleiben: Positionen den Fraktionen zuschreiben, nicht bewerten.
- In summary nur, worum es ging. Die Positionen gehören in positions: für \
jede Fraktion, die zu dem Thema gesprochen hat, ein Eintrag mit ihren \
Redner:innen und einem Satz zu ihrer Position. Partei-Kennungen und Namen \
exakt so übernehmen, wie sie in den Auszügen stehen.
- Der Positionssatz steht direkt hinter dem Parteinamen: ohne Subjekt, mit \
dem Verb im Plural ("Wenden sich gegen …", "Fordern …", "Begrüßen …"), nicht \
"Die Fraktion kritisierte …".
- Kleinere Punkte ohne eigenen Abschnitt als kurze Stichworte in other_topics.
- Die Kennungen (A1, A2, …) gehören NUR in agenda_refs, nie in Überschriften, \
Zusammenfassungen oder other_topics.

Tagesordnungspunkte:
{agenda}
"""


def format_vote_prompt(parliament: str, votes_block: str) -> str:
    return VOTE_ENRICHMENT_PROMPT.format(
        parliament=parliament, topics=topic_legend(), votes=votes_block
    )


def format_session_prompt(parliament: str, day: str, agenda_block: str) -> str:
    return SESSION_SUMMARY_PROMPT.format(
        parliament=parliament, day=day, topics=topic_legend(), agenda=agenda_block
    )

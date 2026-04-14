# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Static context and party metadata for study sessions.

The study uses fictional parties whose data does not live in Firebase. Every
place in the guided exploration pipeline that would normally look up party
names and descriptions via ``aget_parties_for_context`` instead calls into
this module when the ``context_id`` identifies a study topic.

Keeping this data in a single Python module avoids leaking fictional parties
into production Firebase and makes the study self-contained.
"""

from __future__ import annotations

from src.guided_exploration.agents.party_context import PartyInfo

# Context ids for the two study topics.
STUDY_CONTEXT_PREFIX = "study-"
STUDY_CONTEXT_KLIMA = "study-klimaschutz"
STUDY_CONTEXT_SOZIAL = "study-soziale-gerechtigkeit"

# Display names shown in prompts and the UI.
STUDY_CONTEXT_NAMES: dict[str, str] = {
    STUDY_CONTEXT_KLIMA: "Klimaschutz (Studie)",
    STUDY_CONTEXT_SOZIAL: "Soziale Gerechtigkeit (Studie)",
}

# The five fictional parties used in the study. Ordered from left to right
# on the political spectrum for consistency with the position data.
STUDY_PARTY_IDS: list[str] = ["merkur", "venus", "mars", "jupiter", "saturn"]

STUDY_PARTIES: dict[str, PartyInfo] = {
    "merkur": PartyInfo(
        party_id="merkur",
        name="Merkur",
        long_name="Merkur-Partei",
        description=(
            "Linke, umverteilungsorientierte Partei. Starker Fokus auf "
            "soziale Gerechtigkeit, staatliche Daseinsvorsorge und "
            "ambitionierten Klimaschutz mit sozialem Ausgleich."
        ),
    ),
    "venus": PartyInfo(
        party_id="venus",
        name="Venus",
        long_name="Venus-Partei",
        description=(
            "Grün-sozialdemokratische Partei. Ambitionierte Klimaziele, "
            "starker Sozialstaat, progressive Gesellschaftspolitik und "
            "pragmatische Umsetzung."
        ),
    ),
    "mars": PartyInfo(
        party_id="mars",
        name="Mars",
        long_name="Mars-Partei",
        description=(
            "Pragmatisch-konservative Partei mit wirtschaftsfreundlichem "
            "Profil. Stabilität, Standort Deutschland, kontrollierte "
            "Migrationspolitik und marktwirtschaftlicher Klimaschutz."
        ),
    ),
    "jupiter": PartyInfo(
        party_id="jupiter",
        name="Jupiter",
        long_name="Jupiter-Partei",
        description=(
            "Marktliberale Partei. Freiheit, Innovation, "
            "Technologieoffenheit, Bürokratieabbau und kapitalgedeckte "
            "Altersvorsorge."
        ),
    ),
    "saturn": PartyInfo(
        party_id="saturn",
        name="Saturn",
        long_name="Saturn-Partei",
        description=(
            "Rechtspopulistisch-nationalkonservative Partei. Nationale "
            "Souveränität, Ablehnung internationaler Klimaverpflichtungen, "
            "restriktive Migrationspolitik und Skepsis gegenüber "
            "politischen Eliten."
        ),
    ),
}


def is_study_context(context_id: str) -> bool:
    """Whether this context_id identifies a study session."""
    return context_id.startswith(STUDY_CONTEXT_PREFIX)


def get_study_context_info(
    context_id: str,
    party_ids: list[str] | None = None,
) -> tuple[str, dict[str, PartyInfo]]:
    """
    Return (context_name, parties_info) for a study context, bypassing Firebase.

    If ``party_ids`` is given, only those parties are returned (in order).
    Otherwise all five study parties are returned.
    """
    context_name = STUDY_CONTEXT_NAMES.get(context_id, context_id)
    if party_ids is None:
        parties = dict(STUDY_PARTIES)
    else:
        parties = {pid: STUDY_PARTIES[pid] for pid in party_ids if pid in STUDY_PARTIES}
    return context_name, parties


def get_study_topic(context_id: str) -> str:
    """
    Extract the topic suffix from a study context id.

    Example: ``study-klimaschutz`` -> ``klimaschutz``.
    """
    return context_id[len(STUDY_CONTEXT_PREFIX):]

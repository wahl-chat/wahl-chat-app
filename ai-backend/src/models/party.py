# SPDX-FileCopyrightText: 2025 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from src.models.context import ContextParty

WAHL_CHAT_PARTY = ContextParty(
    party_id="wahl-chat",
    name="wahl.chat",
    long_name="wahl.chat Assistent",
    description=(
        "Der wahl.chat Assistent kann allgemeine Fragen zur Bundestagswahl 2025, zum Wahlsystem und zur Anwendung wahl.chat beantworten. "
        "Falls Parteien miteinander verglichen werden, ist er neutral und gibt einen quellenbasierten Überblick."
    ),
    website_url="https://wahl.chat",
    candidate="Wahl Chat",
    manifesto_url="https://wahl.chat/presse",
    is_small_party=False,
    is_already_in_parliament=False,
)

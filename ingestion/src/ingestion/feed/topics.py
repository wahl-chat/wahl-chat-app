# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Topic vocabulary for digest items.

The keys are the web's ``TOPIC_TITLES`` (``web/components/topics/topics.data.ts``)
plus ``other``, so the feed's filter chips and colours need no second
taxonomy. A test asserts the two key sets stay in sync.

Declared as a ``Literal`` rather than an ``Enum``: these types are handed to
Gemini structured output, where langchain-google-genai mishandles Python enums.
"""

from __future__ import annotations

from typing import Literal, get_args

DigestTopic = Literal[
    "economy_finance",
    "social_labor",
    "education_research",
    "climate_environment",
    "health_care",
    "digitalization_tech",
    "migration_integration",
    "security_justice",
    "foreign_policy_europe",
    "transport_infrastructure",
    "housing_rent",
    "other",
]

DIGEST_TOPICS: tuple[str, ...] = get_args(DigestTopic)

# German labels for the prompts, so the model maps content onto the same
# meaning the UI shows for each key.
TOPIC_LABELS_DE: dict[str, str] = {
    "economy_finance": "Wirtschaft und Finanzen",
    "social_labor": "Soziales und Arbeit",
    "education_research": "Bildung und Forschung",
    "climate_environment": "Klimaschutz und Umwelt",
    "health_care": "Gesundheit und Pflege",
    "digitalization_tech": "Digitalisierung und Technologie",
    "migration_integration": "Migration und Integration",
    "security_justice": "Innere Sicherheit und Justiz",
    "foreign_policy_europe": "Außenpolitik und Europa",
    "transport_infrastructure": "Verkehr und Infrastruktur",
    "housing_rent": "Wohnungsbau und Mieten",
    "other": "Weitere Themen",
}


def topic_legend() -> str:
    """The ``key: label`` list the prompts present to the model."""
    return "\n".join(f"- {key}: {TOPIC_LABELS_DE[key]}" for key in DIGEST_TOPICS)

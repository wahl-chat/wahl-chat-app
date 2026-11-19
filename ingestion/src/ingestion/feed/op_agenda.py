# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""A debate's recordings on openparliament.tv: its agenda item's page.

The corpus holds openparliament.tv's bulk data, which carries no agenda item
id. The site's session API lists each sitting's agenda items with their
official label ("Tagesordnungspunkt 22", "Zusatzpunkt 18"), which maps onto the
same ``top22`` / ``zp18`` slug a debate is keyed by.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Optional

import requests

from ingestion.speech_key import agenda_slug_from_top_id

logger = logging.getLogger(__name__)

OP_BASE_URL = "https://de.openparliament.tv"
_TIMEOUT_SECONDS = 30

# ``(Wahlperiode, Sitzung)`` → ``{agenda slug: page URL}``.
OpAgendaPages = Callable[[tuple[int, int]], Optional[dict[str, str]]]


def session_id(session: tuple[int, int]) -> str:
    """openparliament.tv's id of a Bundestag sitting: ``DE-0210090``."""
    ep, number = session
    return f"DE-{ep:03d}{number:04d}"


def agenda_pages(session_json: dict[str, Any]) -> dict[str, str]:
    """Each numbered agenda item's page, by its slug. Items without a number
    (Sitzungseröffnung, a bare "TOP ") belong to no debate."""
    relationships = (session_json.get("data") or {}).get("relationships") or {}
    items = (relationships.get("agendaItems") or {}).get("data") or []
    pages: dict[str, str] = {}
    for item in items:
        slug = agenda_slug_from_top_id(
            str((item.get("attributes") or {}).get("officialTitle") or "")
        )
        if slug and item.get("id"):
            # "20a" and "20b" share a slug, as they share a debate.
            pages.setdefault(slug, f"{OP_BASE_URL}/agendaItem/DE-{item['id']}")
    return pages


def op_agenda_lookup(
    get_json: Optional[Callable[[str], dict[str, Any]]] = None,
) -> OpAgendaPages:
    """Look up a sitting's agenda item pages, once per sitting per run.

    None when the lookup fails, so the debates keep no link and a later run
    asks again; an empty dict is an answer (the site lists no such item yet).
    """
    fetch = get_json or _get_json
    answers: dict[tuple[int, int], Optional[dict[str, str]]] = {}

    def lookup(session: tuple[int, int]) -> Optional[dict[str, str]]:
        if session not in answers:
            url = f"{OP_BASE_URL}/api/v1/session/{session_id(session)}"
            try:
                answers[session] = agenda_pages(fetch(url))
            except Exception as exc:  # noqa: BLE001 — retried next run
                logger.warning("No openparliament.tv agenda for %s: %s", url, exc)
                answers[session] = None
        return answers[session]

    return lookup


def _get_json(url: str) -> dict[str, Any]:
    response = requests.get(url, timeout=_TIMEOUT_SECONDS)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError(f"unexpected response from {url}")
    return data

# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Press coverage of a procedure, next to our own sources.

A procedure get_process returns also brings up to three web results about
it: from our preferred news outlets or a Fraktion's own site, dated near its
steps, and naming its subject. The model sees outlet coverage as tier
"press" and a party's own page as tier "party_site", that party's statement.
Votes and party positions get none.
``GENERIC_CHAT_WEB_CONTEXT=off`` turns it off.
"""

from __future__ import annotations

import logging
import os
import re
import time
from datetime import date, timedelta
from typing import Iterable, Optional
from urllib.parse import urlsplit

from pydantic_ai.framing import wrap

from src.generic_chat import web_search as web
from src.generic_chat.schemas import (
    GenericChatDeps,
    Tier,
    NumberedDocument,
    ProcessResult,
    WebResult,
)
from wahlchat_common.answer_rules import PREFERRED_OUTLETS

logger = logging.getLogger(__name__)

ENV = "GENERIC_CHAT_WEB_CONTEXT"
# A Fraktion's own site speaks for that party.
FRAKTION_SITES: dict[str, str] = {
    "cducsu.de": "cdu",
    "csu-landesgruppe.de": "cdu",
    "spdfraktion.de": "spd",
    "gruene-bundestag.de": "gruene",
    "linksfraktion.de": "linke",
    "afdbundestag.de": "afd",
}
# A party's own site speaks for it too, wherever a web result comes from.
# Each party we have data for adds its website_url (see party_sites).
PARTY_SITES: dict[str, str] = {
    **FRAKTION_SITES,
    "cdu.de": "cdu",
    "csu.de": "cdu",
    "spd.de": "spd",
    "gruene.de": "gruene",
    "die-linke.de": "linke",
    "afd.de": "afd",
    "dielinkebt.de": "linke",
    "junge-union.de": "cdu",
    "jusos.de": "spd",
    "gruene-jugend.de": "gruene",
    "linksjugend-solid.de": "linke",
    "julis.de": "fdp",
}
# Sites of parties we have no data for: domain to the party's name. Parties
# on the 2025 Bundestag or 2024 European ballot, plus the larger Landtag-only
# ones; each domain matches the party's filing with the Bundeswahlleiterin or
# names the party on its own pages.
EXTRA_PARTY_SITES: dict[str, str] = {
    "diebasis-partei.de": "dieBasis",
    "die-partei.de": "Die PARTEI",
    "pdh.eu": "Partei der Humanisten",
    "buendnis-c.de": "Bündnis C",
    "mlpd.de": "MLPD",
    "menschlichewelt.de": "Menschliche Welt",
    "partei-des-fortschritts.de": "Partei des Fortschritts",
    "gleichheit.de": "Sozialistische Gleichheitspartei",
    "verjuengungsforschung.de": "Partei für Verjüngungsforschung",
    "buendnis-deutschland.de": "Bündnis Deutschland",
    "mera25.de": "MERA25",
    "werteunion.de": "WerteUnion",
    "gerechtigkeitspartei.de": "Team Todenhöfer",
    "ssw.de": "SSW",
    "bayernpartei.de": "Bayernpartei",
    "bueso.de": "BüSo",
    "wählefamilie.de": "Familien-Partei Deutschlands",
    "xn--whlefamilie-l8a.de": "Familien-Partei Deutschlands",
    "waehlefamilie.de": "Familien-Partei Deutschlands",
    "die-heimat.de": "Die Heimat",
    "tierschutz-hier.de": "TIERSCHUTZ hier!",
    "bigpartei.de": "BIG",
    "dkp.de": "DKP",
    "aktion-bfg.de": "Aktion Bürger für Gerechtigkeit",
    "dava-eu.org": "DAVA",
    "klimaliste.org": "Klimaliste Deutschland",
    "v-partei.de": "V-Partei³",
    "bvb-fw.de": "BVB / Freie Wähler",
    "freie-sachsen.info": "Freie Sachsen",
}
# bundestag.de is the record our corpus already holds, not coverage of it.
PRESS_SITES = tuple(d for d in PREFERRED_OUTLETS if d != "bundestag.de") + tuple(FRAKTION_SITES)
# Coverage of a law changes slowly; follow-up turns reuse it.
_CACHE_S = 3600.0
_CACHE_SIZE = 256
_cache: dict[str, tuple[float, list[WebResult]]] = {}
MAX_PRESS = 3
# Coverage that leads up to a law starts before its first step.
_BEFORE = timedelta(days=30)
_AFTER = timedelta(days=14)
_GENERIC = frozenset(
    {
        "gesetz", "gesetzes", "gesetzentwurf", "entwurf", "eines", "änderung",
        "änderungen", "reform", "weiterer", "vorschriften", "bundestag",
        "antrag", "beschlussempfehlung", "fraktion", "zur", "über",
    }
)


def enabled() -> bool:
    return os.getenv(ENV, "on") != "off"


def _day(value: Optional[str]) -> Optional[date]:
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def subject_words(title: str) -> list[str]:
    """Stems of the title's telling words: 'Nachrichtendienstrechts' → 'nachrich'."""
    words = re.findall(r"[\wäöüßÄÖÜ]{6,}", title.casefold())
    return sorted({w[:8] for w in words if w not in _GENERIC})


def _short_title(title: str) -> str:
    title = re.sub(r"\(.*?\)", "", title)
    title = re.sub(r"^(Entwurf eines |Gesetzentwurf (der|zur) )", "", title, flags=re.I)
    return " ".join(title.split())[:120]


def matching(
    results: Iterable[WebResult], words: list[str], start: date, end: date
) -> list[WebResult]:
    """Dated inside the window and naming the subject; at most ``MAX_PRESS``."""
    out: list[WebResult] = []
    for result in results:
        day = _day(result.date)
        if day is None or not start <= day <= end:
            continue
        text = f"{result.title} {result.snippet}".casefold()
        if words and not any(w in text for w in words):
            continue
        out.append(result)
    return out[:MAX_PRESS]


def _host(url: str) -> str:
    host = (urlsplit(url if "//" in url else f"//{url}").hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def party_sites(deps: GenericChatDeps) -> dict[str, str]:
    """Domain to party_id: the hand-kept sites plus every party's website."""
    sites = dict(PARTY_SITES)
    for party in deps.parties:
        host = _host(party.website_url or "")
        if host:
            sites.setdefault(host, party.party_id)
    return sites


def _matches(domain: str, site: str) -> bool:
    return domain == site or domain.endswith("." + site)


def party_of(deps: GenericChatDeps, domain: str) -> tuple[Optional[str], Optional[str]]:
    """The party a site speaks for: (party_id, name). A party without data
    has a name but no id."""
    domain = _host(domain)
    for site, party_id in party_sites(deps).items():
        if _matches(domain, site):
            return party_id, deps.party_name(party_id)
    for site, name in EXTRA_PARTY_SITES.items():
        if _matches(domain, site):
            return None, name
    return None, None


def register_results(
    deps: GenericChatDeps, results: list[WebResult], tier: Optional[Tier] = None
) -> list[NumberedDocument]:
    """Web results as sources; a party's own page is that party's statement,
    everything else gets ``tier``."""
    documents = []
    for result in results:
        title = web.safe_title(result.title)
        party_id, party = party_of(deps, result.domain)
        entry: dict = {
            "source": title,
            "page": 1,
            "document_publish_date": result.date,
            "url": result.url,
            "source_document": result.domain,
            "source_type": "web",
        }
        if party_id:
            entry["party_id"] = party_id
        if not party:
            entry["preferred_outlet"] = result.preferred
        number = deps.sources.register(entry)
        documents.append(
            NumberedDocument(
                id=number,
                source_type="web",
                title=title,
                date=result.date,
                party=party,
                outlet=result.domain,
                preferred_outlet=None if party else result.preferred,
                tier="party_site" if party else tier,
                text=wrap(web.WEB_SNIPPET_TAG, result.snippet),
            )
        )
    return documents


async def _search(query: str) -> list[WebResult]:
    now = time.monotonic()
    hit = _cache.get(query)
    if hit is not None and now - hit[0] < _CACHE_S:
        return hit[1]
    results, note = await web.search_sites(query, PRESS_SITES)
    if note is None:
        if len(_cache) >= _CACHE_SIZE:
            _cache.pop(next(iter(_cache)))
        _cache[query] = (now, results)
    return results


async def add_press(deps: GenericChatDeps, result: ProcessResult) -> None:
    """Append the procedure's coverage to its documents, once per turn. A
    feed button's answer is cached, so it stands on our data alone."""
    procedure = result.procedure
    if not enabled() or procedure is None or deps.preset is not None:
        return
    if procedure.vorgang_id in deps.press_seen:
        return
    deps.press_seen.add(procedure.vorgang_id)
    days = [d for d in (_day(s.date) for s in result.steps) if d is not None]
    if not days:
        return
    results = await _search(f"{_short_title(procedure.title)} Bundestag")
    found = matching(
        results, subject_words(procedure.title), min(days) - _BEFORE, max(days) + _AFTER
    )
    logger.info(
        "press: %d of %d results for procedure %s", len(found), len(results), procedure.vorgang_id
    )
    result.documents = [*result.documents, *register_results(deps, found, "press")]

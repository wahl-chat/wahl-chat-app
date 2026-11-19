# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Press coverage of a procedure next to our sources."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

import src.generic_chat.web_context as web_context
from src.generic_chat.schemas import ProcessResult, ProcessStep, ProcessInfo, WebResult
from tests.generic_chat.conftest import make_deps


def hit(title: str, day: str | None, snippet: str = "") -> WebResult:
    return WebResult(title=title, url=f"https://www.tagesschau.de/{title}", snippet=snippet,
                     date=day, domain="tagesschau.de", preferred=True)


def test_only_dated_coverage_naming_the_subject_stays() -> None:
    words = web_context.subject_words("Gesetz zur Reform des Nachrichtendienstrechts")
    assert words == ["nachrich"]
    kept = web_context.matching(
        [
            hit("BND bekommt neue Befugnisse", "2026-11-13", "Das Nachrichtendienstrecht …"),
            hit("Nachrichtendienste 2019", "2019-01-01"),  # too old
            hit("Haushalt", "2026-11-13", "Schuldenbremse"),  # other subject
            hit("Nachrichtendienst ohne Datum", None),
        ],
        words, date(2026, 9, 1), date(2026, 11, 27),
    )
    assert [r.title for r in kept] == ["BND bekommt neue Befugnisse"]


@pytest.fixture
def sites(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    queries: list[str] = []

    async def search_sites(query: str, domains: Any, recency: Any = None) -> Any:
        queries.append(query)
        return [hit(f"Reform {i}", "2026-11-14", "Nachrichtendienstrecht") for i in range(5)], None

    monkeypatch.setattr(web_context.web, "search_sites", search_sites)
    return queries


def _procedure() -> ProcessResult:
    return ProcessResult(
        procedure=ProcessInfo.model_construct(vorgang_id="338341", title="Gesetz zur Reform des Nachrichtendienstrechts"),
        steps=[ProcessStep.model_construct(date="2026-09-24"), ProcessStep.model_construct(date="2026-11-13")],
    )


async def test_switched_off_or_a_feed_button_fetches_nothing(
    sites: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(web_context.ENV, "off")
    result = _procedure()
    await web_context.add_press(make_deps(), result)
    monkeypatch.setenv(web_context.ENV, "on")
    button = make_deps()
    button.preset = "ask"
    await web_context.add_press(button, result)
    assert sites == [] and result.documents == []


async def test_a_procedure_brings_three_press_documents_once(
    sites: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(web_context.ENV, "on")
    deps = make_deps()
    first, again = _procedure(), _procedure()
    await web_context.add_press(deps, first)
    await web_context.add_press(deps, again)
    assert len(sites) == 1
    assert [d.tier for d in first.documents] == ["press"] * 3 and again.documents == []


def _result(url: str) -> WebResult:
    from src.generic_chat.web_search import domain_of

    return WebResult(title="Seite", url=url, snippet="…", date="2026-11-13",
                     domain=domain_of(url), preferred=False)


def test_a_small_partys_own_site_speaks_for_it() -> None:
    deps = make_deps()
    deps.parties[2] = deps.parties[2].model_copy(update={"website_url": "https://voltdeutschland.org/"})
    [doc] = web_context.register_results(deps, [_result("https://www.voltdeutschland.org/presse")], "press")
    entry = deps.sources.entries[doc.id]
    assert (doc.tier, doc.party, entry.get("party_id")) == ("party_site", "Volt", "volt")
    assert "preferred_outlet" not in entry


def test_a_party_without_data_speaks_without_an_icon(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(web_context.EXTRA_PARTY_SITES, "die-partei.de", "Die PARTEI")
    deps = make_deps()
    [doc] = web_context.register_results(deps, [_result("https://die-partei.de/x")], "press")
    entry = deps.sources.entries[doc.id]
    assert (doc.tier, doc.party) == ("party_site", "Die PARTEI")
    assert "party_id" not in entry and "preferred_outlet" not in entry


@pytest.mark.parametrize(
    "url", ["https://xn--whlefamilie-l8a.de/a", "https://www.gartenpartei.eu/b", "https://bayern.die-partei.de/c"]
)
def test_listed_party_sites_match_with_subdomains(url: str) -> None:
    from src.generic_chat.web_search import domain_of

    assert web_context.party_of(make_deps(), domain_of(url))[1] is not None


@pytest.mark.parametrize("domain", ["dkp.de", "mlpd.de", "die-heimat.de", "freie-sachsen.info", "der-dritte-weg.info"])
def test_parties_named_extremist_stay_external(domain: str) -> None:
    assert web_context.party_of(make_deps(), domain) == (None, None)


def test_youth_wing_speaks_for_its_party() -> None:
    deps = make_deps()
    assert web_context.party_of(deps, "www.jusos.de")[0] == "spd"


def test_any_other_site_stays_external() -> None:
    deps = make_deps()
    [doc] = web_context.register_results(deps, [_result("https://www.youtube.com/watch")], "press")
    entry = deps.sources.entries[doc.id]
    assert (doc.tier, doc.party, entry["preferred_outlet"]) == ("press", None, False)


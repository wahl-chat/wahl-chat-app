"""From the Bundestag's DIP records to the bill sheet's document.

Everything here is copied from the official record; where the record does not
say how the cover prints something, the draft gets a note for the reviewer
rather than a guess.
"""

from __future__ import annotations

import re

# A vote on a committee's recommendation is a vote "in the version of" it:
# the bill or motion itself is the document, the recommendation is `votedIn`.
VOTED_IN_TYPES = ("Beschlussempfehlung und Bericht", "Beschlussempfehlung", "Bericht")
# When a vote links several Drucksachen, the first of these types is the one
# the puzzle shows.
DOCUMENT_TYPES = ("Gesetzentwurf", "Antrag", "Verordnung", "Entschließungsantrag")


def number_from_url(url: str) -> str | None:
    """'https://dserver.bundestag.de/btd/21/062/2106278.pdf' becomes '21/6278'."""
    match = re.search(r"/btd/(\d+)/\d+/(\d+)\.pdf$", url)
    if not match:
        return None
    period, file = match.groups()
    if not file.startswith(period):
        return None
    return f"{period}/{int(file[len(period) :])}"


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def submitter(record: dict) -> tuple[dict | None, list[str]]:
    """Who submitted it, as the Drucksache's cover prints it, and any notes.

    The cover uses the genitive: "Gesetzentwurf der Bundesregierung",
    "Antrag der Abgeordneten A, B, … und der Fraktion der AfD".
    """
    urheber = [_clean(u.get("titel", "")) for u in record.get("urheber") or []]
    if urheber == ["Bundesregierung"]:
        return {"initiator": "der Bundesregierung"}, []
    if urheber == ["Bundesrat"]:
        return {"initiator": "des Bundesrates"}, []
    if len(urheber) == 1 and urheber[0].startswith("Fraktion "):
        fraktion = urheber[0].removeprefix("Fraktion ")
        names = [
            _clean(author["autor_titel"])
            for author in record.get("autoren_anzeige") or []
            if author.get("autor_titel")
        ]
        if not names:
            return {"initiator": f"der {urheber[0]}"}, []
        result: dict = {"fraktion": fraktion, "members": names}
        signed = record.get("autoren_anzahl") or len(names)
        if signed > len(names):
            result["memberCount"] = signed
        return result, []
    if urheber and all(name.startswith("Fraktion ") for name in urheber):
        joint = " und ".join(name.removeprefix("Fraktion ") for name in urheber)
        return {"initiator": f"der Fraktionen {joint}"}, [
            "submitted by several Fraktionen: check the wording on the cover"
        ]
    return None, [f"unexpected submitter {urheber}: copy it from the cover"]


def committee_genitive(name: str) -> str | None:
    """'Ausschuss für Wirtschaft und Energie' becomes 'des Ausschusses für …'.

    Every Bundestag committee is an "-ausschuss", which takes "-es".
    """
    name = _clean(name)
    match = re.match(r"^(\S*[Aa]usschuss)\b(.*)$", name)
    if not match:
        return None
    return f"des {match.group(1)}es{match.group(2)}"


def voted_in(record: dict) -> tuple[dict | None, list[str]]:
    """The committee recommendation the vote was taken on, as the sheet names it."""
    urheber = [u.get("titel", "") for u in record.get("urheber") or []]
    committee = committee_genitive(urheber[0]) if len(urheber) == 1 else None
    if not committee:
        return None, [
            f"{record.get('dokumentnummer')}: unexpected author {urheber} of the "
            "recommendation: write the 'votedIn' label by hand"
        ]
    kind = (
        "Bericht"
        if record.get("drucksachetyp") == "Bericht"
        else ("Beschlussempfehlung")
    )
    return {
        "label": f"{kind} {committee}",
        "number": record["dokumentnummer"],
        "url": (record.get("fundstelle") or {}).get("pdf_url"),
    }, []


def document(records: list[dict]) -> tuple[dict | None, list[str]]:
    """The puzzle's `document` from the Drucksachen a vote links to, and notes."""
    notes: list[str] = []
    main = [r for r in records if r.get("drucksachetyp") not in VOTED_IN_TYPES]
    recommendations = [r for r in records if r.get("drucksachetyp") in VOTED_IN_TYPES]
    if not main:
        return None, ["no bill or motion linked: the briefing uses the plain layout"]

    def rank(record: dict) -> tuple[int, int]:
        kind = record.get("drucksachetyp")
        order = DOCUMENT_TYPES.index(kind) if kind in DOCUMENT_TYPES else 99
        number = int(str(record.get("dokumentnummer", "0/0")).split("/")[-1])
        return order, number

    main.sort(key=rank)
    chosen = main[0]
    if len(main) > 1:
        others = ", ".join(
            f"{r.get('dokumentnummer')} ({r.get('drucksachetyp')})" for r in main[1:]
        )
        notes.append(
            f"also linked: {others}; check that {chosen.get('dokumentnummer')} "
            "is the one voted on"
        )

    who, who_notes = submitter(chosen)
    notes += who_notes
    if who is None:
        return None, notes
    result = {
        "type": chosen.get("drucksachetyp"),
        "number": chosen.get("dokumentnummer"),
        "date": chosen.get("datum"),
        **who,
        "title": _clean(chosen.get("titel", "")),
        "url": (chosen.get("fundstelle") or {}).get("pdf_url"),
    }
    if recommendations:
        recommendations.sort(key=rank)
        voted, voted_notes = voted_in(recommendations[0])
        notes += voted_notes
        if voted:
            result["votedIn"] = voted
        if len(recommendations) > 1:
            notes.append("several recommendations linked: check which one was voted on")
    return result, notes

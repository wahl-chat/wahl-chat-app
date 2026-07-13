# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""MdB-Stammdaten lookup — load speaker→party mapping from the Bundestag master file.

Absorbed from ~/Downloads/bundestag_speeches/mdb.py.
Security swap: xml.etree.ElementTree → defusedxml.ElementTree to block
entity-expansion attacks when loading the 15 MB MdB-Stammdaten XML.

Public API:
  load_mdb_lookup(path) -> dict[str, dict]
    Builds {by_id: {id: record}, by_name: {normalized_name: record}} from
    the MdB-Stammdaten XML. Returns empty lookups if the file is missing
    (graceful degradation — XML <fraktion> is the primary party source).

  mdb_party_for_speech(xml_speech, mdb_lookup) -> str | None
    Resolves party by speaker_xml_id first, then by normalized name.

  mdb_record_for_speaker_name(xml_speech, mdb_lookup) -> dict | None
    Returns the unique MdB record for a speaker name (by_name lookup).
"""

from __future__ import annotations

from pathlib import Path

import defusedxml.ElementTree as ElementTree  # blocks entity-expansion / billion-laughs

from .utils import normalize_name_for_lookup, normalize_party, normalize_whitespace, parse_int


def name_from_mdb_entry(name_entry) -> str | None:
    parts = [name_entry.findtext("VORNAME"), name_entry.findtext("NACHNAME")]
    return normalize_whitespace(" ".join(part for part in parts if part))


def latest_fraction_party(mdb) -> str | None:
    parties: list[tuple[int, str]] = []
    for term in mdb.findall("WAHLPERIODEN/WAHLPERIODE"):
        term_number = parse_int(term.findtext("WP"))
        for institution in term.findall("INSTITUTIONEN/INSTITUTION"):
            if normalize_whitespace(institution.findtext("INSART_LANG")) != "Fraktion/Gruppe":
                continue
            party = normalize_party(institution.findtext("INS_LANG"))
            if party:
                parties.append((term_number, party))

    if not parties:
        return None
    return max(parties, key=lambda item: item[0])[1]


def parse_mdb_record(mdb) -> dict:
    names = [name_from_mdb_entry(name) for name in mdb.findall("NAMEN/NAME")]
    party = normalize_party(mdb.findtext("BIOGRAFISCHE_ANGABEN/PARTEI_KURZ")) or latest_fraction_party(mdb)
    return {
        "id": normalize_whitespace(mdb.findtext("ID")),
        "names": [name for name in names if name],
        "party": party,
    }


def load_mdb_lookup(path) -> dict:
    """Load the MdB-Stammdaten XML into {by_id, by_name} lookup dicts.

    Returns empty lookups (not an error) when the file is absent — the
    connector degrades gracefully to XML <fraktion> as the sole party source.
    Raises defusedxml.EntitiesForbidden on entity-expansion attacks.
    """
    path = Path(path)
    if not path.exists():
        print(f"Warning: MDB Stammdaten file not found: {path}")
        return {"by_id": {}, "by_name": {}}

    root = ElementTree.parse(str(path)).getroot()
    by_id: dict[str, dict] = {}
    name_candidates: dict[str, list[dict]] = {}

    for mdb in root.findall("MDB"):
        record = parse_mdb_record(mdb)
        if record["id"]:
            by_id[record["id"]] = record

        for name in record["names"]:
            lookup_name = normalize_name_for_lookup(name)
            if lookup_name:
                name_candidates.setdefault(lookup_name, []).append(record)

    by_name: dict[str, dict] = {}
    for name, records in name_candidates.items():
        if len({record["id"] for record in records}) == 1:
            by_name[name] = records[0]

    return {"by_id": by_id, "by_name": by_name}


def mdb_party_for_speech(xml_speech: dict, mdb_lookup: dict) -> str | None:
    """Resolve party for a speech dict via the MdB lookup.

    Resolution order:
      1. by_id[speaker_xml_id].party
      2. by_name[normalize_name_for_lookup(speaker_name)].party
      3. None (caller falls back to XML <fraktion>)
    """
    person_id = xml_speech.get("speaker_xml_id")
    if person_id:
        record = mdb_lookup["by_id"].get(person_id)
        if record and record["party"]:
            return record["party"]

    speaker_name = normalize_name_for_lookup(xml_speech.get("speaker_name"))
    if speaker_name:
        record = mdb_lookup["by_name"].get(speaker_name)
        if record and record["party"]:
            return record["party"]

    return None


def mdb_record_for_speaker_name(xml_speech: dict, mdb_lookup: dict) -> dict | None:
    """Return the unique MdB record for a speaker name (by_name lookup), or None."""
    speaker_name = normalize_name_for_lookup(xml_speech.get("speaker_name"))
    if not speaker_name:
        return None
    return mdb_lookup["by_name"].get(speaker_name)

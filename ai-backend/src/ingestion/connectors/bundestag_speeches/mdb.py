# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""MdB-Stammdaten lookup — load speaker→party mapping from the Bundestag master file.

Uses defusedxml.ElementTree to block entity-expansion attacks when loading
the 15 MB MdB-Stammdaten XML.

Public API:
  load_mdb_lookup(path) -> dict[str, dict]
    Builds {by_id: {id: record}, by_name: {normalized_name: record}} from
    the MdB-Stammdaten XML. Returns empty lookups if the file is missing
    (graceful degradation — for bulk/backfill callers that tolerate it).

  ensure_mdb_lookup(path) -> dict[str, dict]
    Live-run variant: downloads the file first if absent, then loads it, and
    RAISES on an empty result. A scheduled speech run must resolve
    minister/president speakers, so silent degradation to "unbekannt" is a
    fail-loud stop rather than a warning.

  download_mdb_stammdaten(dest) -> Path
    Fetches + extracts the OpenData ZIP to ``dest`` (transient failures retried,
    a 404 fails fast — the blob rotated).

  mdb_party_for_speech(xml_speech, mdb_lookup) -> str | None
    Resolves party by speaker_xml_id first, then by normalized name.

  mdb_record_for_speaker_name(xml_speech, mdb_lookup) -> dict | None
    Returns the unique MdB record for a speaker name (by_name lookup).
"""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import defusedxml.ElementTree as ElementTree  # blocks entity-expansion / billion-laughs
import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .constants import MDB_STAMMDATEN_FILE, MDB_STAMMDATEN_URL
from .utils import (
    normalize_name_for_lookup,
    normalize_party,
    normalize_whitespace,
    parse_int,
)

# Default on-disk path (relative to ai-backend/). mdb.py sits at the same depth
# as connector.py, so the parents[4] anchor matches the connectors' _MDB_PATH.
_DEFAULT_MDB_PATH: Path = Path(__file__).resolve().parents[4] / MDB_STAMMDATEN_FILE

# The single XML member inside the OpenData ZIP.
_MDB_ZIP_MEMBER = "MDB_STAMMDATEN.XML"


class StammdatenUnavailableError(RuntimeError):
    """MdB-Stammdaten could not be obtained, or loaded to a non-empty lookup.

    Fail-loud signal for the live speech path: without this master data,
    empty-``<fraktion>`` speakers (ministers, the president) all resolve to
    "unbekannt", so ingesting would quietly poison party attribution.
    """


@retry(
    # Retry transient network faults and 5xx. A 404 is raised as
    # StammdatenUnavailableError below (not in this set), so it fails fast.
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
def _fetch_zip_bytes(url: str) -> bytes:
    resp = httpx.get(url, timeout=60.0, follow_redirects=True)
    if resp.status_code == 404:
        raise StammdatenUnavailableError(
            f"MdB-Stammdaten not found at {url} (HTTP 404) — the OpenData blob "
            "was likely rotated; get the current link from "
            "https://www.bundestag.de/services/opendata"
        )
    resp.raise_for_status()  # 5xx → HTTPStatusError → retried
    return resp.content


def download_mdb_stammdaten(
    dest: Path | str = _DEFAULT_MDB_PATH, *, url: str = MDB_STAMMDATEN_URL
) -> Path:
    """Download the OpenData ZIP and extract MDB_STAMMDATEN.XML to ``dest``.

    In-memory extraction (no temp file). Transient failures are retried with
    backoff; a 404 fails fast (rotated blob — see StammdatenUnavailableError).
    """
    dest = Path(dest)
    print(f"Fetching MdB-Stammdaten from {url} …", file=sys.stderr)
    payload = _fetch_zip_bytes(url)
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        try:
            data = zf.read(_MDB_ZIP_MEMBER)
        except KeyError as exc:
            raise StammdatenUnavailableError(
                f"{_MDB_ZIP_MEMBER} not present in the ZIP at {url}"
            ) from exc
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    print(f"Saved MdB-Stammdaten to {dest} ({len(data)} bytes).", file=sys.stderr)
    return dest


def ensure_mdb_lookup(
    path: Path | str = _DEFAULT_MDB_PATH, *, download: bool = True
) -> dict:
    """Load the MdB-Stammdaten lookup, fetching the file first when absent.

    The live-run counterpart to load_mdb_lookup: it downloads on a cache miss
    and REQUIRES a non-empty result, raising StammdatenUnavailableError
    otherwise. ``download=False`` skips the fetch (used where a caller wants
    the strict emptiness check without network access).
    """
    path = Path(path)
    if download and not path.exists():
        download_mdb_stammdaten(path)
    lookup = load_mdb_lookup(path)
    if not lookup["by_id"] and not lookup["by_name"]:
        raise StammdatenUnavailableError(
            f"MdB-Stammdaten lookup is empty (file: {path}). Refusing to ingest "
            "speeches: every empty-<fraktion> speaker would degrade to 'unbekannt'."
        )
    return lookup


def name_from_mdb_entry(name_entry) -> str | None:
    parts = [name_entry.findtext("VORNAME"), name_entry.findtext("NACHNAME")]
    return normalize_whitespace(" ".join(part for part in parts if part))


def latest_fraction_party(mdb) -> str | None:
    parties: list[tuple[int, str]] = []
    for term in mdb.findall("WAHLPERIODEN/WAHLPERIODE"):
        term_number = parse_int(term.findtext("WP"))
        for institution in term.findall("INSTITUTIONEN/INSTITUTION"):
            if (
                normalize_whitespace(institution.findtext("INSART_LANG"))
                != "Fraktion/Gruppe"
            ):
                continue
            party = normalize_party(institution.findtext("INS_LANG"))
            if party:
                parties.append((term_number, party))

    if not parties:
        return None
    return max(parties, key=lambda item: item[0])[1]


def parse_mdb_record(mdb) -> dict:
    names = [name_from_mdb_entry(name) for name in mdb.findall("NAMEN/NAME")]
    party = normalize_party(
        mdb.findtext("BIOGRAFISCHE_ANGABEN/PARTEI_KURZ")
    ) or latest_fraction_party(mdb)
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


def main() -> None:
    """Pre-fetch the MdB-Stammdaten XML to the default path (host dev convenience).

    Idempotent: skips the download when the file is already present (delete it
    to refresh). Wired to `make fetch-mdb-stammdaten`.
    """
    if _DEFAULT_MDB_PATH.exists():
        print(
            f"MdB-Stammdaten already present ({_DEFAULT_MDB_PATH}) — skipping.",
            file=sys.stderr,
        )
        return
    download_mdb_stammdaten(_DEFAULT_MDB_PATH)


if __name__ == "__main__":
    main()

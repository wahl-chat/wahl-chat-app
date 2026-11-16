# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""The DIP reads the procedures job needs, batched by id.

DIP accepts repeated ``f.id`` / ``f.vorgang`` / ``f.dokumentnummer`` filters,
so a backfill is a few hundred paged calls rather than one per Vorgang.
Every function raises on a failed call: callers retry the item next run
instead of treating a failure as "nothing there".
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator
from datetime import date
from typing import Any, Protocol

from ingestion.connectors.bundestag_speeches.client import DipClient

_ID_BATCH = 50
_POSITION_BATCH = 20


class DipReader(Protocol):
    """What the job reads from DIP; tests pass a fake."""

    def plenary_vorgang_types(self, wahlperiode: int) -> dict[str, str]: ...

    def vorgang_ids_of_types(self, wahlperiode: int, types: Iterable[str]) -> set[str]: ...

    def updated_vorgang_ids(self, wahlperiode: int, since: str) -> set[str]: ...

    def vorgaenge(self, ids: Iterable[str]) -> dict[str, dict[str, Any]]: ...

    def positions(self, ids: Iterable[str]) -> dict[str, list[dict[str, Any]]]: ...

    def positions_on(self, day: date) -> list[dict[str, Any]]: ...

    def protocol_activities(self, protocol_number: str) -> list[dict[str, Any]]: ...

    def drucksache_vorgaenge(self, numbers: Iterable[str]) -> dict[str, list[str]]: ...

    def drucksache_texts(self, numbers: Iterable[str]) -> dict[str, dict[str, Any]]: ...


def _batches(items: Iterable[str], size: int) -> Iterator[list[str]]:
    batch: list[str] = []
    for item in sorted(set(items)):
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


class LiveDip:
    """DipReader over the paced, retrying :class:`DipClient`."""

    def __init__(self, client: DipClient) -> None:
        self._client = client
        self._protocol_ids: dict[str, str] = {}

    def _documents(self, endpoint: str, params: dict[str, Any]) -> Iterator[dict[str, Any]]:
        seen: set[str] = set()
        for page in self._client.pages(endpoint, params):
            for doc in page.get("documents") or []:
                # A cursor page can repeat the last document of the one before.
                if doc["id"] not in seen:
                    seen.add(doc["id"])
                    yield doc

    def plenary_vorgang_types(self, wahlperiode: int) -> dict[str, str]:
        """Vorgang id → Vorgangstyp for every Vorgang with a BT plenary stage."""
        params = {
            "f.wahlperiode": wahlperiode,
            "f.zuordnung": "BT",
            "f.dokumentart": "Plenarprotokoll",
        }
        return {
            str(doc["vorgang_id"]): doc["vorgangstyp"]
            for doc in self._documents("/vorgangsposition", params)
        }

    def vorgang_ids_of_types(self, wahlperiode: int, types: Iterable[str]) -> set[str]:
        ids: set[str] = set()
        for vorgangstyp in sorted(types):
            params = {"f.wahlperiode": wahlperiode, "f.vorgangstyp": vorgangstyp}
            ids.update(str(doc["id"]) for doc in self._documents("/vorgang", params))
        return ids

    def updated_vorgang_ids(self, wahlperiode: int, since: str) -> set[str]:
        """Vorgänge DIP changed since ``since``, by their own or a stage's
        ``aktualisiert`` (a new stage may not touch the Vorgang)."""
        params = {"f.wahlperiode": wahlperiode, "f.aktualisiert.start": since}
        ids = {str(doc["id"]) for doc in self._documents("/vorgang", params)}
        ids.update(
            str(doc["vorgang_id"])
            for doc in self._documents("/vorgangsposition", params)
        )
        return ids

    def vorgaenge(self, ids: Iterable[str]) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for batch in _batches(ids, _ID_BATCH):
            for doc in self._documents("/vorgang", {"f.id": batch}):
                out[str(doc["id"])] = doc
        return out

    def positions(self, ids: Iterable[str]) -> dict[str, list[dict[str, Any]]]:
        wanted = set(ids)
        out: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for batch in _batches(wanted, _POSITION_BATCH):
            for doc in self._documents("/vorgangsposition", {"f.vorgang": batch}):
                out[str(doc["vorgang_id"])].append(doc)
        return {vid: out.get(vid, []) for vid in wanted}

    def positions_on(self, day: date) -> list[dict[str, Any]]:
        params = {
            "f.datum.start": day.isoformat(),
            "f.datum.end": day.isoformat(),
            "f.zuordnung": "BT",
        }
        return list(self._documents("/vorgangsposition", params))

    def _protocol_id(self, protocol_number: str) -> str:
        if protocol_number not in self._protocol_ids:
            docs = list(
                self._documents(
                    "/plenarprotokoll",
                    {"f.dokumentnummer": protocol_number, "f.zuordnung": "BT"},
                )
            )
            if len(docs) != 1:
                raise LookupError(
                    f"Plenarprotokoll {protocol_number}: {len(docs)} matches in DIP"
                )
            self._protocol_ids[protocol_number] = str(docs[0]["id"])
        return self._protocol_ids[protocol_number]

    def protocol_activities(self, protocol_number: str) -> list[dict[str, Any]]:
        """Every activity DIP indexed for one BT Plenarprotokoll ('21/91')."""
        params = {"f.plenarprotokoll": self._protocol_id(protocol_number)}
        return [
            doc
            for doc in self._documents("/aktivitaet", params)
            if (doc.get("fundstelle") or {}).get("dokumentnummer") == protocol_number
        ]

    def drucksache_vorgaenge(self, numbers: Iterable[str]) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for batch in _batches(numbers, _ID_BATCH):
            params = {"f.dokumentnummer": batch, "f.zuordnung": "BT"}
            for doc in self._documents("/drucksache", params):
                out[doc["dokumentnummer"]] = sorted(
                    str(ref["id"]) for ref in doc.get("vorgangsbezug") or []
                )
        return out

    def drucksache_texts(self, numbers: Iterable[str]) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        # Texts are large; small batches keep each response modest.
        for batch in _batches(numbers, 10):
            params = {"f.dokumentnummer": batch, "f.zuordnung": "BT"}
            for doc in self._documents("/drucksache-text", params):
                out[doc["dokumentnummer"]] = doc
        return out

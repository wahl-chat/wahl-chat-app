# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Tests for the live-Firestore election lookup and the backend switch.

Two things matter here. First, the switch must be EXPLICIT: nothing may silently
change which authority is trusted. Second, the Firestore backend must enforce the
same gate as the file backend — it shares ``build_fixture`` precisely so a missing
``region_path`` cannot slip through on the container path and write chunks no query
can reach.

Also asserts the GDPR Art. 9 wall at the behavioural level: the reader touches only
``contexts`` and its ``parties`` subcollection, never ``users`` and never a
collection-group query. ``scripts/check_gdpr_wall.py`` enforces the same statically.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from ingestion.connectors.manifesto_uploads import firestore_fixtures
from ingestion.connectors.manifesto_uploads.election_fixtures import (
    FixtureLookupError,
    load_election,
)
from ingestion.connectors.manifesto_uploads.firestore_fixtures import (
    load_election_from_firestore,
)

_CTX = "landtagswahl-sachsen-anhalt-2026"

_CONTEXT_DOC = {
    "context_id": _CTX,
    "name": "Landtagswahl Sachsen-Anhalt 2026",
    "date": "2026-09-06",
    "region_path": ["DE", "DE-ST"],
    "level": "state",
}


# ---------------------------------------------------------------------------
# Fakes — record every collection path touched.
# ---------------------------------------------------------------------------


class _Snapshot:
    def __init__(self, data: dict | None) -> None:
        self._data = data
        self.exists = data is not None

    def to_dict(self) -> dict | None:
        return self._data


class _PartyDoc:
    def __init__(self, doc_id: str) -> None:
        self.id = doc_id


class _DocRef:
    def __init__(self, client: "_FakeFirestore", doc_id: str) -> None:
        self._client = client
        self._doc_id = doc_id

    def get(self) -> _Snapshot:
        if self._client.raise_on_get:
            raise RuntimeError("deadline exceeded")
        return _Snapshot(self._client.contexts.get(self._doc_id))

    def collection(self, name: str):  # noqa: ANN201
        self._client.paths.append(f"contexts/{self._doc_id}/{name}")
        if self._client.raise_on_parties:
            raise RuntimeError("permission denied")
        return _PartyCollection(self._client.parties)


class _PartyCollection:
    def __init__(self, party_ids: list[str]) -> None:
        self._party_ids = party_ids

    def stream(self):  # noqa: ANN201
        return iter(_PartyDoc(pid) for pid in self._party_ids)


class _Collection:
    def __init__(self, client: "_FakeFirestore") -> None:
        self._client = client

    def document(self, doc_id: str) -> _DocRef:
        return _DocRef(self._client, doc_id)


class _FakeFirestore:
    def __init__(
        self,
        contexts: dict | None = None,
        parties: list[str] | None = None,
        *,
        raise_on_get: bool = False,
        raise_on_parties: bool = False,
    ) -> None:
        self.contexts = contexts if contexts is not None else {_CTX: dict(_CONTEXT_DOC)}
        self.parties = (
            parties if parties is not None else ["spd", "cdu", "gartenpartei"]
        )
        self.raise_on_get = raise_on_get
        self.raise_on_parties = raise_on_parties
        self.paths: list[str] = []

    def collection(self, name: str) -> _Collection:
        self.paths.append(name)
        return _Collection(self)

    def collection_group(self, name: str):  # noqa: ANN201
        raise AssertionError(
            "collection_group is forbidden in ingestion code (GDPR Art. 9 wall)"
        )


@pytest.fixture()
def fake_firestore(monkeypatch: pytest.MonkeyPatch):
    """Install a fake client and return a factory for configuring it."""

    def _install(**kwargs) -> _FakeFirestore:  # noqa: ANN003
        client = _FakeFirestore(**kwargs)
        monkeypatch.setattr(firestore_fixtures, "_client", lambda: client)
        return client

    return _install


# ===========================================================================
# Reading the live database
# ===========================================================================


class TestLoadFromFirestore:
    """The context doc plus its parties subcollection yield the same fixture."""

    def test_resolves_region_level_date_and_parties(self, fake_firestore) -> None:
        fake_firestore()
        fixture = load_election_from_firestore(_CTX)
        assert fixture.region == "DE-ST"
        assert fixture.level == "state"
        assert fixture.election_date == date(2026, 9, 6)
        assert fixture.party_ids == frozenset({"spd", "cdu", "gartenpartei"})

    def test_party_ids_come_from_subcollection_doc_ids(self, fake_firestore) -> None:
        fake_firestore(parties=["spd", "volt"])
        assert load_election_from_firestore(_CTX).party_ids == frozenset(
            {"spd", "volt"}
        )

    def test_timestamp_date_is_accepted(self, fake_firestore) -> None:
        # A hand-edited doc (or the console) stores date as a timestamp, not a string.
        fake_firestore(
            contexts={
                _CTX: {
                    **_CONTEXT_DOC,
                    "date": datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc),
                }
            }
        )
        assert load_election_from_firestore(_CTX).election_date == date(2026, 9, 6)

    def test_absent_context_raises_with_a_pointer_to_seeding(
        self, fake_firestore
    ) -> None:
        fake_firestore(contexts={})
        with pytest.raises(FixtureLookupError, match="unknown election"):
            load_election_from_firestore(_CTX)

    def test_no_parties_raises(self, fake_firestore) -> None:
        fake_firestore(parties=[])
        with pytest.raises(FixtureLookupError, match="declares no parties"):
            load_election_from_firestore(_CTX)


class TestSameGateAsTheFileBackend:
    """The container path must not be a weaker gate than the local one."""

    def test_missing_region_path_still_raises(self, fake_firestore) -> None:
        doc = {k: v for k, v in _CONTEXT_DOC.items() if k != "region_path"}
        fake_firestore(contexts={_CTX: doc})
        with pytest.raises(FixtureLookupError, match="no region_path"):
            load_election_from_firestore(_CTX)

    def test_missing_level_still_raises(self, fake_firestore) -> None:
        doc = {k: v for k, v in _CONTEXT_DOC.items() if k != "level"}
        fake_firestore(contexts={_CTX: doc})
        with pytest.raises(FixtureLookupError, match="level"):
            load_election_from_firestore(_CTX)

    def test_missing_date_still_raises(self, fake_firestore) -> None:
        doc = {k: v for k, v in _CONTEXT_DOC.items() if k != "date"}
        fake_firestore(contexts={_CTX: doc})
        with pytest.raises(FixtureLookupError, match="no date"):
            load_election_from_firestore(_CTX)


class TestTransportFailures:
    """A database problem is a per-item skip, never a dead run."""

    def test_context_read_failure_is_wrapped(self, fake_firestore) -> None:
        fake_firestore(raise_on_get=True)
        with pytest.raises(
            FixtureLookupError, match="could not read Firestore context"
        ):
            load_election_from_firestore(_CTX)

    def test_parties_read_failure_is_wrapped(self, fake_firestore) -> None:
        fake_firestore(raise_on_parties=True)
        with pytest.raises(FixtureLookupError, match="could not read parties"):
            load_election_from_firestore(_CTX)


class TestGdprWall:
    """Only public election config is read — never user data."""

    def test_touches_only_contexts_and_its_parties(self, fake_firestore) -> None:
        client = fake_firestore()
        load_election_from_firestore(_CTX)
        assert client.paths == ["contexts", f"contexts/{_CTX}/parties"]
        assert not any("users" in path for path in client.paths)

    def test_never_issues_a_collection_group_query(self, fake_firestore) -> None:
        # The fake raises on collection_group; reaching it would fail the test.
        fake_firestore()
        load_election_from_firestore(_CTX)


# ===========================================================================
# Backend switch
# ===========================================================================


class TestBackendSwitch:
    """Explicit selection only — no implicit fallback between authorities."""

    def test_defaults_to_the_seed_files(
        self, monkeypatch: pytest.MonkeyPatch, fake_firestore
    ) -> None:
        monkeypatch.delenv("ELECTION_FIXTURES_SOURCE", raising=False)
        client = fake_firestore(contexts={})  # would raise if consulted
        assert load_election(_CTX, env="dev").region == "DE-ST"
        assert client.paths == []

    def test_files_is_accepted_explicitly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ELECTION_FIXTURES_SOURCE", "files")
        assert load_election(_CTX, env="dev").region == "DE-ST"

    def test_firestore_backend_is_used_when_selected(
        self, monkeypatch: pytest.MonkeyPatch, fake_firestore
    ) -> None:
        monkeypatch.setenv("ELECTION_FIXTURES_SOURCE", "firestore")
        client = fake_firestore(parties=["spd"])
        fixture = load_election(_CTX)
        assert fixture.party_ids == frozenset({"spd"})
        assert client.paths[0] == "contexts"

    @pytest.mark.parametrize("value", ["FIRESTORE", " firestore "])
    def test_selection_is_case_and_space_insensitive(
        self, monkeypatch: pytest.MonkeyPatch, fake_firestore, value: str
    ) -> None:
        monkeypatch.setenv("ELECTION_FIXTURES_SOURCE", value)
        fake_firestore(parties=["spd"])
        assert load_election(_CTX).party_ids == frozenset({"spd"})

    def test_unknown_backend_raises_rather_than_guessing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ELECTION_FIXTURES_SOURCE", "postgres")
        with pytest.raises(FixtureLookupError, match="not a known backend"):
            load_election(_CTX)

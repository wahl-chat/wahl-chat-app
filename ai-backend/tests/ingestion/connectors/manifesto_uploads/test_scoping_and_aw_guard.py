# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Tests for the election-date floor and the AW-already-has-it guard.

The floor carries a genuine hazard. Retirement works by "stored but no longer in the
work-list", so a filter that merely narrows the work-list would, without care, make
every past election's manifestos look retired and delete them. The tests below pin
the safe behaviour: out-of-scope documents are neither ingested NOR retired.

The AW guard is the missing direction of the overlap policy. The AW connector's
post_upsert removes an uploaded copy when AW ingests the same programme, which only
helps when AW ingestion runs AFTER the upload. This guard covers the other order —
AW already in the corpus — where the upload would otherwise be a silent duplicate.
"""

from __future__ import annotations

import types
from datetime import date
from pathlib import Path
from typing import Optional

import pytest

from src.ingestion.connectors.manifesto_uploads import election_fixtures
from src.ingestion.connectors.manifesto_uploads.connector import (
    ManifestoUploadsConnector,
    in_scope,
    resolve_since_floor,
)

# Two fully-seeded elections written to a temp fixture dir: one still to come, one
# already held. Deliberately NOT the repo fixtures — Baden-Württemberg and co. carry
# no region_path yet, so they are UNRESOLVABLE and therefore in-scope by design (see
# test_unresolvable_documents_count_as_in_scope), which would hide the very
# distinction these tests exist to make.
_FUTURE_CTX = "landtagswahl-futureland-2026"
_PAST_CTX = "landtagswahl-pastland-2026"
_ST = f"public/{_FUTURE_CTX}/spd/Wahlprogramm-SPD_2026-06-01.pdf"
_BW = f"public/{_PAST_CTX}/spd/Wahlprogramm-Past_2026-01-20.pdf"


@pytest.fixture(autouse=True)
def _seeded_elections(tmp_path_factory, monkeypatch: pytest.MonkeyPatch):
    """Point the fixture lookup at two valid elections with different dates."""
    import json

    env_dir = tmp_path_factory.mktemp("fixtures") / "dev"
    env_dir.mkdir()
    (env_dir / "contexts.json").write_text(
        json.dumps(
            {
                _FUTURE_CTX: {
                    "name": "Landtagswahl Futureland 2026",
                    "date": "2026-09-06",
                    "region_path": ["DE", "DE-FL"],
                    "level": "state",
                },
                _PAST_CTX: {
                    "name": "Landtagswahl Pastland 2026",
                    "date": "2026-03-08",
                    "region_path": ["DE", "DE-PL"],
                    "level": "state",
                },
            }
        ),
        encoding="utf-8",
    )
    for ctx in (_FUTURE_CTX, _PAST_CTX):
        (env_dir / f"parties_{ctx}.json").write_text(
            json.dumps({"spd": {}, "cdu": {}, "gartenpartei": {}}), encoding="utf-8"
        )
    monkeypatch.setattr(election_fixtures, "fixture_dir", lambda env=None: env_dir)
    election_fixtures._contexts.cache_clear()
    election_fixtures._parties.cache_clear()
    yield
    election_fixtures._contexts.cache_clear()
    election_fixtures._parties.cache_clear()


# ===========================================================================
# resolve_since_floor
# ===========================================================================


class TestResolveSinceFloor:
    """No floor by default; a bad one is loud, never silently ignored."""

    def test_no_floor_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MANIFESTO_UPLOADS_SINCE", raising=False)
        assert resolve_since_floor() is None

    def test_explicit_value_wins_over_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MANIFESTO_UPLOADS_SINCE", "2020-01-01")
        assert resolve_since_floor("2026-07-29") == date(2026, 7, 29)

    def test_env_is_read_when_no_explicit_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MANIFESTO_UPLOADS_SINCE", "2026-07-29")
        assert resolve_since_floor() == date(2026, 7, 29)

    @pytest.mark.parametrize("blank", ["", "   "])
    def test_blank_means_no_floor(
        self, monkeypatch: pytest.MonkeyPatch, blank: str
    ) -> None:
        monkeypatch.setenv("MANIFESTO_UPLOADS_SINCE", blank)
        assert resolve_since_floor() is None

    @pytest.mark.parametrize("bad", ["29.07.2026", "2026-7-29", "today", "2026-13-01"])
    def test_invalid_date_raises(self, bad: str) -> None:
        with pytest.raises(ValueError, match="must be an ISO date"):
            resolve_since_floor(bad)


# ===========================================================================
# in_scope
# ===========================================================================


class TestInScope:
    """Scope is decided by the ELECTION date, not the document date."""

    def test_everything_in_scope_without_a_floor(self) -> None:
        assert in_scope(_ST, None, "dev") is True
        assert in_scope(_BW, None, "dev") is True

    def test_future_election_passes_a_floor(self) -> None:
        assert in_scope(_ST, date(2026, 7, 29), "dev") is True

    def test_past_election_fails_a_floor(self) -> None:
        # Pastland voted 2026-03-08, before the floor.
        assert in_scope(_BW, date(2026, 7, 29), "dev") is False

    def test_boundary_is_inclusive(self) -> None:
        assert in_scope(_ST, date(2026, 9, 6), "dev") is True
        assert in_scope(_ST, date(2026, 9, 7), "dev") is False

    def test_document_date_is_irrelevant(self) -> None:
        # This document is from 2019 but its ELECTION is in 2026,
        # so a 2026 floor keeps it: the floor scopes elections, not documents.
        gartenpartei = f"public/{_FUTURE_CTX}/gartenpartei/Satzung_2019-11-30.pdf"
        assert in_scope(gartenpartei, date(2026, 7, 29), "dev") is True

    @pytest.mark.parametrize(
        "unresolvable",
        [
            "public/landtagswahl-nowhere-2026/spd/Programm_2026-01-01.pdf",
            f"public/{_FUTURE_CTX}/nichtantretende/P_2026-01-01.pdf",
        ],
    )
    def test_unresolvable_documents_count_as_in_scope(self, unresolvable: str) -> None:
        # The floor must not become a way to silently swallow a broken path or an
        # unseeded election — those must reach normalize() and fail loudly there.
        assert in_scope(unresolvable, date(2026, 7, 29), "dev") is True


# ===========================================================================
# discover — the filter must never cause a deletion
# ===========================================================================


class _Qdrant:
    """Serves the stored-object-path scroll and a filter-aware count."""

    def __init__(self, stored: list[str], non_upload: int = 0) -> None:
        self._stored = stored
        self._non_upload = non_upload

    def scroll(self, **kwargs):  # noqa: ANN003, ANN201
        points = [
            types.SimpleNamespace(
                id=str(i), payload={"meta": {"storage_object_path": p}}
            )
            for i, p in enumerate(self._stored)
        ]
        return points, None

    def count(self, **kwargs):  # noqa: ANN003, ANN201
        return types.SimpleNamespace(count=self._non_upload)


def _connector(
    tmp_path: Path,
    entries: list[str],
    stored: Optional[list[str]] = None,
    since: Optional[date] = None,
    non_upload: int = 0,
) -> ManifestoUploadsConnector:
    manifest = tmp_path / "dev.txt"
    manifest.write_text("\n".join(entries) + "\n", encoding="utf-8")
    connector = ManifestoUploadsConnector(
        manifest_path=manifest, env="dev", since=since
    )
    connector.bind_store(_Qdrant(stored or [], non_upload), "c")
    return connector


class TestDiscoverWithAFloor:
    """The dangerous interaction: filtering must not read as "should not exist"."""

    def test_in_scope_documents_are_offered(self, tmp_path: Path) -> None:
        connector = _connector(tmp_path, [_ST, _BW], since=date(2026, 7, 29))
        assert connector.discover(None) == [_ST]

    def test_out_of_scope_document_already_stored_is_NOT_retired(
        self, tmp_path: Path
    ) -> None:
        # BW is listed AND stored, but below the floor. It must simply be left
        # alone — not offered, and above all not retired.
        connector = _connector(
            tmp_path, [_ST, _BW], stored=[_ST, _BW], since=date(2026, 7, 29)
        )
        assert connector.discover(None) == [_ST]

    def test_out_of_scope_and_unlisted_document_is_NOT_retired(
        self, tmp_path: Path
    ) -> None:
        # The worst case: BW dropped from the manifest AND below the floor. Retiring
        # it here would delete a past election's manifestos the moment a floor is set,
        # so the floor wins and it is left untouched.
        connector = _connector(
            tmp_path, [_ST], stored=[_ST, _BW], since=date(2026, 7, 29)
        )
        assert connector.discover(None) == [_ST]

    def test_in_scope_unlisted_document_IS_still_retired(self, tmp_path: Path) -> None:
        # Retirement must keep working for documents the floor does not exclude.
        other_st = _ST.replace("/spd/", "/cdu/")
        connector = _connector(
            tmp_path, [_ST], stored=[_ST, other_st], since=date(2026, 7, 29)
        )
        assert connector.discover(None) == sorted([_ST, other_st])
        assert connector.fetch(other_st)["retired"] is True

    def test_without_a_floor_everything_behaves_as_before(self, tmp_path: Path) -> None:
        connector = _connector(tmp_path, [_ST], stored=[_ST, _BW])
        assert connector.discover(None) == sorted([_ST, _BW])
        assert connector.fetch(_BW)["retired"] is True

    def test_floor_comes_from_the_env_when_not_passed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MANIFESTO_UPLOADS_SINCE", "2026-07-29")
        manifest = tmp_path / "dev.txt"
        manifest.write_text(f"{_ST}\n{_BW}\n", encoding="utf-8")
        connector = ManifestoUploadsConnector(manifest_path=manifest, env="dev")
        connector.bind_store(_Qdrant([]), "c")
        assert connector.discover(None) == [_ST]


# ===========================================================================
# The AW-already-has-it guard
# ===========================================================================


_PAGES = {"pages": [(1, "Aus dem Wahlprogramm. " * 40)], "total_pages": 1}


class TestAwGuard:
    """An upload is skipped when AW already carries that party's programme."""

    def test_ingests_normally_when_aw_has_nothing(self, tmp_path: Path) -> None:
        connector = _connector(tmp_path, [_ST], non_upload=0)
        connector.discover(None)
        records = connector.normalize({"object_path": _ST, **_PAGES})
        assert records and records[0].party_id == "spd"

    def test_skips_when_an_aw_copy_exists(self, tmp_path: Path) -> None:
        connector = _connector(tmp_path, [_ST], non_upload=214)
        connector.discover(None)
        with pytest.raises(ValueError, match="Abgeordnetenwatch already carries"):
            connector.normalize({"object_path": _ST, **_PAGES})

    def test_skipping_raises_rather_than_returning_no_chunks(
        self, tmp_path: Path
    ) -> None:
        # Raising is a per-item SKIP: the runner leaves any stored chunks intact.
        # Returning [] would be an authoritative "this should not exist" and delete
        # them — removal is the AW connector's post_upsert job, not this guard's, so
        # only one mechanism ever deletes.
        connector = _connector(tmp_path, [_ST], stored=[_ST], non_upload=214)
        connector.discover(None)
        with pytest.raises(ValueError):
            connector.normalize({"object_path": _ST, **_PAGES})

    def test_guard_filter_excludes_our_own_uploads(self, tmp_path: Path) -> None:
        """The count must ignore source="upload", or a re-run blocks itself."""
        captured: dict = {}

        class _Recorder(_Qdrant):
            def count(self, **kwargs):  # noqa: ANN003, ANN201
                captured["filter"] = kwargs.get("count_filter")
                return types.SimpleNamespace(count=0)

        manifest = tmp_path / "dev.txt"
        manifest.write_text(f"{_ST}\n", encoding="utf-8")
        connector = ManifestoUploadsConnector(manifest_path=manifest, env="dev")
        connector.bind_store(_Recorder([]), "c")
        connector.discover(None)
        connector.normalize({"object_path": _ST, **_PAGES})

        flt = captured["filter"]
        must = {
            c.key: getattr(c.match, "value", None)
            for c in flt.must
            if hasattr(c, "match")
        }
        assert must["source_type"] == "party_manifesto"
        assert must["party_id"] == "spd"
        assert must["region"] == "DE-FL"
        # source="upload" is EXCLUDED, so our own chunks never trip the guard.
        assert [(c.key, c.match.value) for c in flt.must_not] == [("source", "upload")]

    def test_no_store_bound_means_no_guard(self, tmp_path: Path) -> None:
        # A bare connector (unit tests, no runner) must still ingest.
        manifest = tmp_path / "dev.txt"
        manifest.write_text(f"{_ST}\n", encoding="utf-8")
        connector = ManifestoUploadsConnector(manifest_path=manifest, env="dev")
        connector.discover(None)
        assert connector.normalize({"object_path": _ST, **_PAGES})

    def test_a_failing_count_does_not_block_the_ingest(self, tmp_path: Path) -> None:
        # An unavailable store must not silently suppress documents.
        class _Broken(_Qdrant):
            def count(self, **kwargs):  # noqa: ANN003, ANN201
                raise RuntimeError("unavailable")

        manifest = tmp_path / "dev.txt"
        manifest.write_text(f"{_ST}\n", encoding="utf-8")
        connector = ManifestoUploadsConnector(manifest_path=manifest, env="dev")
        connector.bind_store(_Broken([]), "c")
        connector.discover(None)
        assert connector.normalize({"object_path": _ST, **_PAGES})

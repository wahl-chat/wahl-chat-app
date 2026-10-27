# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Tests for the bucket-listing work-list and the work-list backend switch.

The bucket backend exists so a scheduled Job notices an upload or a deletion
without a redeploy — the manifest ships inside the image. That makes the listing a
DESIRED-STATE statement, which is the dangerous part: anything that turns a real
listing into an empty or truncated one would retire live documents. So the tests
here concentrate on the two failure directions:

  * junk in the shared ``public/`` prefix (icons, other assets) must be ignored
    rather than fail the run — the bucket is not ours alone;
  * a listing that cannot be trusted (transport error, or content present but
    nothing recognisable) must RAISE, never degrade to "nothing should exist".
"""

from __future__ import annotations

import types

import pytest

from ingestion.connectors.manifesto_uploads import bucket_listing
from ingestion.connectors.manifesto_uploads.bucket_listing import (
    BucketListingError,
    list_uploaded_objects,
)
from ingestion.connectors.manifesto_uploads.connector import work_list

_CTX = "landtagswahl-sachsen-anhalt-2026"
_SPD = f"public/{_CTX}/wahlprogramme/spd/Wahlprogramm-SPD_2026-06-01.pdf"
_CDU = f"public/{_CTX}/wahlprogramme/cdu/Wahlprogramm-CDU_2026-03-24.pdf"


class _FakeStorage:
    """Minimal Storage client returning named blobs."""

    def __init__(self, names: list[str], *, raise_on_list: bool = False) -> None:
        self._names = names
        self._raise = raise_on_list
        self.calls: list[tuple[str, str]] = []

    def list_blobs(self, bucket_name: str, prefix: str = ""):  # noqa: ANN201
        self.calls.append((bucket_name, prefix))
        if self._raise:
            raise RuntimeError("403 Forbidden")
        return [types.SimpleNamespace(name=n) for n in self._names]


# ===========================================================================
# Listing
# ===========================================================================


class TestListing:
    """Manifesto PDFs are returned; everything else in the prefix is ignored."""

    def test_returns_sorted_object_paths(self) -> None:
        client = _FakeStorage([_CDU, _SPD])
        assert list_uploaded_objects("dev", client=client) == sorted([_SPD, _CDU])

    def test_lists_the_env_bucket_under_the_public_prefix(self) -> None:
        client = _FakeStorage([_SPD])
        list_uploaded_objects("prod", client=client)
        assert client.calls == [("wahl-chat.firebasestorage.app", "public/")]

    def test_duplicates_collapse(self) -> None:
        client = _FakeStorage([_SPD, _SPD])
        assert list_uploaded_objects("dev", client=client) == [_SPD]

    @pytest.mark.parametrize(
        "junk",
        [
            "public/icons/spd.png",  # a context icon, not a manifesto
            f"public/{_CTX}/wahlprogramme/spd/",  # directory placeholder
            f"public/{_CTX}/wahlprogramme/spd/no-date.pdf",  # missing the date suffix
            f"public/{_CTX}/wahlprogramme/spd/notes_2026-06-01.txt",  # not a PDF
            f"public/{_CTX}/wahlprogramme/loose_2026-06-01.pdf",  # no party segment
            f"public/{_CTX}/spd/Programm_2026-06-01.pdf",  # no document class folder
            f"public/{_CTX}/programme/spd/P_2026-06-01.pdf",  # unknown class folder
        ],
    )
    def test_non_manifesto_objects_are_ignored_not_fatal(self, junk: str) -> None:
        # public/ is shared and world-readable; an unrelated asset must not stop
        # every manifesto from being ingested.
        client = _FakeStorage([_SPD, junk])
        assert list_uploaded_objects("dev", client=client) == [_SPD]

    def test_an_empty_bucket_yields_an_empty_list(self) -> None:
        # Genuinely nothing uploaded yet — legitimate, and there is nothing stored
        # to retire either.
        assert list_uploaded_objects("dev", client=_FakeStorage([])) == []


# ===========================================================================
# Refusing to produce an untrustworthy work-list
# ===========================================================================


class TestUntrustworthyListings:
    """An unreliable listing must raise, because empty means "retire everything"."""

    def test_transport_failure_raises(self) -> None:
        client = _FakeStorage([], raise_on_list=True)
        with pytest.raises(BucketListingError, match="could not list"):
            list_uploaded_objects("dev", client=client)

    def test_content_present_but_nothing_recognised_raises(self) -> None:
        # Wrong bucket, or the layout changed. Treating this as "nothing should
        # exist" would delete every uploaded manifesto in the corpus.
        client = _FakeStorage(["public/icons/a.png", "public/legal/imprint.html"])
        with pytest.raises(BucketListingError, match="none match"):
            list_uploaded_objects("dev", client=client)

    def test_not_a_valueerror_so_the_runner_does_not_skip_and_continue(self) -> None:
        # ValueError is the framework's per-item skip signal; a missing work-list is
        # a whole-run failure and must abort loudly instead.
        assert not issubclass(BucketListingError, ValueError)


# ===========================================================================
# Backend switch
# ===========================================================================


class TestWorkListSwitch:
    """Explicit selection; the manifest stays the credential-free default."""

    def test_defaults_to_the_manifest(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("MANIFESTO_UPLOADS_SOURCE", raising=False)
        manifest = tmp_path / "dev.txt"
        manifest.write_text(f"{_SPD}\n", encoding="utf-8")

        def _boom(*a, **k):  # noqa: ANN002, ANN003, ANN202
            raise AssertionError("the bucket must not be listed on the manifest path")

        monkeypatch.setattr(bucket_listing, "list_uploaded_objects", _boom)
        assert work_list(manifest, "dev") == [_SPD]

    def test_bucket_backend_is_used_when_selected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MANIFESTO_UPLOADS_SOURCE", "bucket")
        monkeypatch.setattr(
            bucket_listing, "_client", lambda env=None: _FakeStorage([_SPD, _CDU])
        )
        assert work_list(None, "dev") == sorted([_SPD, _CDU])

    @pytest.mark.parametrize("value", ["BUCKET", " bucket "])
    def test_selection_is_case_and_space_insensitive(
        self, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        monkeypatch.setenv("MANIFESTO_UPLOADS_SOURCE", value)
        monkeypatch.setattr(
            bucket_listing, "_client", lambda env=None: _FakeStorage([_SPD])
        )
        assert work_list(None, "dev") == [_SPD]

    def test_unknown_backend_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MANIFESTO_UPLOADS_SOURCE", "s3")
        with pytest.raises(ValueError, match="not a known work-list backend"):
            work_list(None, "dev")

    def test_bucket_backend_starts_for_an_env_that_ships_no_manifest(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """prod has no checked-in manifest, and the bucket backend must not need one.

        The CLI used to preflight the manifest whatever backend was selected, so a
        bucket-backed ENV=prod run exited before it ever listed the bucket.
        """
        monkeypatch.setenv("MANIFESTO_UPLOADS_SOURCE", "bucket")
        monkeypatch.setattr(
            bucket_listing, "_client", lambda env=None: _FakeStorage([_SPD])
        )
        # An explicitly-passed manifest path that does not exist is also irrelevant
        # on this backend — the bucket is the desired state.
        assert work_list(tmp_path / "prod.txt", "prod") == [_SPD]


def test_bucket_deletion_retires_the_document(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deleting the object is what removes its chunks — the old trigger's behaviour.

    Exercises the connector end of the bucket backend: a document stored in the
    corpus but no longer listed is discovered, flagged retired, and normalises to
    zero chunks, which the runner turns into a footprint delete.
    """
    from ingestion.connectors.manifesto_uploads.connector import (
        ManifestoUploadsConnector,
    )

    monkeypatch.setenv("MANIFESTO_UPLOADS_SOURCE", "bucket")
    # The bucket now holds only SPD; CDU was deleted but its chunks are still stored.
    monkeypatch.setattr(
        bucket_listing, "_client", lambda env=None: _FakeStorage([_SPD])
    )

    class _Qdrant:
        def scroll(self, **kwargs):  # noqa: ANN003, ANN201
            points = [
                types.SimpleNamespace(
                    id=str(i), payload={"meta": {"storage_object_path": path}}
                )
                for i, path in enumerate([_SPD, _CDU])
            ]
            return points, None

    connector = ManifestoUploadsConnector(env="dev")
    connector.bind_store(_Qdrant(), "c")

    assert connector.discover(None) == sorted([_SPD, _CDU])
    raw = connector.fetch(_CDU)
    assert raw["retired"] is True
    assert connector.normalize(raw) == []

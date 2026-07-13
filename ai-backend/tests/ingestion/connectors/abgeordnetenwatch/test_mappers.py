# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Test suite for AW connector pure mappers: polls.py and corpus.py.

Tests are pure — no Firestore, no network, no filesystem writes.
All fixtures come from conftest.py (JSON loaders) and in-line dicts.

Req 2: poll -> Question + Topics
Req 3: poll -> vote_record SourceItemRecord
Req 7: AW external_id namespacing guarantees no collision with Bundestag
"""

from __future__ import annotations

import pytest

try:
    from src.ingestion.ids import compute_source_item_id
    from src.ingestion.schemas import (
        AuthorityTier,
        ChunkRecord,
        SourceItemRecord,
        SourceType,
    )
    from src.matcher.schemas import Question, Topic
except ImportError as _e:
    pytest.skip(
        f"Phase-5 schema teardown: {_e} — these tests are superseded by Plan 05-02+",
        allow_module_level=True,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _poll_fixture() -> dict:
    """Minimal poll fixture matching AW API shape (poll 3602)."""
    return {
        "id": 3602,
        "label": "Corona-Maßnahmen zum Schutz der Bevölkerung",
        "field_poll_date": "2020-05-14",
        "field_intro": "<p>Am 14. Mai 2020 haben die Abgeordneten des Deutschen Bundestages über Corona-Maßnahmen zum Schutz der Bevölkerung abgestimmt.</p>",
        "field_topics": [
            {
                "id": 28,
                "entity_type": "taxonomy_term",
                "label": "Gesundheit",
                "api_url": "https://www.abgeordnetenwatch.de/api/v2/topics/28",
                "abgeordnetenwatch_url": "https://www.abgeordnetenwatch.de/themen-dip21/gesundheit",
            },
            {
                "id": 23,
                "entity_type": "taxonomy_term",
                "label": "Innere Sicherheit",
                "api_url": "https://www.abgeordnetenwatch.de/api/v2/topics/23",
                "abgeordnetenwatch_url": "https://www.abgeordnetenwatch.de/themen-dip21/innere-sicherheit",
            },
            {
                "id": 22,
                "entity_type": "taxonomy_term",
                "label": "Öffentliche Finanzen",
                "api_url": "https://www.abgeordnetenwatch.de/api/v2/topics/22",
                "abgeordnetenwatch_url": "https://www.abgeordnetenwatch.de/themen-dip21/oeffentliche-finanzen-steuern-und-abgaben",
            },
        ],
        "field_related_links": [],
    }


def _topicless_poll() -> dict:
    """Poll with no field_topics — exercises the topic_id=None path."""
    return {
        "id": 9999,
        "label": "Topicless Poll",
        "field_poll_date": "2023-01-15",
        "field_intro": "<p>A poll without topics.</p>",
        "field_topics": [],
        "field_related_links": [],
    }


def _raw_payload(votes: list[dict]) -> dict:
    """Wrap votes into the GCS-stored raw dict shape for chunk_poll."""
    return {
        "poll": _poll_fixture(),
        "votes": votes,
    }


def _make_votes() -> list[dict]:
    """Minimal votes list: 3 FDP yes, 2 SPD no, 1 degenerate fraction=[]."""
    fdp_frac = {
        "id": 14,
        "entity_type": "fraction",
        "label": "FDP (Bundestag 2017 - 2021)",
        "api_url": "https://www.abgeordnetenwatch.de/api/v2/fractions/14",
    }
    spd_frac = {
        "id": 22,
        "entity_type": "fraction",
        "label": "SPD (Bundestag 2017 - 2021)",
        "api_url": "https://www.abgeordnetenwatch.de/api/v2/fractions/22",
    }
    votes = (
        [{"vote": "yes", "fraction": fdp_frac}] * 3
        + [{"vote": "no", "fraction": spd_frac}] * 2
        + [{"vote": "abstain", "fraction": []}]  # degenerate — Req 6
    )
    return votes


# ===========================================================================
# Task 1 tests: polls.py  (poll -> Question + Topics)
# ===========================================================================


class TestPollToQuestion:
    """Tests for polls.poll_to_question."""

    def test_question_id_is_namespaced(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.polls import poll_to_question

        q = poll_to_question(_poll_fixture())
        assert q.question_id == "aw_poll_3602"

    def test_question_text_from_label(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.polls import poll_to_question

        q = poll_to_question(_poll_fixture())
        assert q.text == "Corona-Maßnahmen zum Schutz der Bevölkerung"

    def test_question_topic_id_from_first_topic(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.polls import poll_to_question

        q = poll_to_question(_poll_fixture())
        assert q.topic_id == "aw:gesundheit"

    def test_question_source_is_abgeordnetenwatch(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.polls import poll_to_question

        q = poll_to_question(_poll_fixture())
        assert q.source == "abgeordnetenwatch"

    def test_question_returns_question_instance(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.polls import poll_to_question

        q = poll_to_question(_poll_fixture())
        assert isinstance(q, Question)

    def test_topicless_poll_yields_topic_id_none(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.polls import poll_to_question

        q = poll_to_question(_topicless_poll())
        assert q.topic_id is None

    def test_topicless_poll_question_id_namespaced(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.polls import poll_to_question

        q = poll_to_question(_topicless_poll())
        assert q.question_id == "aw_poll_9999"


class TestTopicsFromPoll:
    """Tests for polls.topics_from_poll."""

    def test_three_topics_from_poll_3602(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.polls import topics_from_poll

        topics = topics_from_poll(_poll_fixture())
        assert len(topics) == 3

    def test_all_topic_ids_namespaced(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.polls import topics_from_poll

        topics = topics_from_poll(_poll_fixture())
        ids = [t.topic_id for t in topics]
        assert "aw:gesundheit" in ids
        assert "aw:innere-sicherheit" in ids
        assert "aw:oeffentliche-finanzen-steuern-und-abgaben" in ids

    def test_all_topics_are_topic_instances(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.polls import topics_from_poll

        topics = topics_from_poll(_poll_fixture())
        for t in topics:
            assert isinstance(t, Topic)

    def test_all_topics_source_is_abgeordnetenwatch(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.polls import topics_from_poll

        topics = topics_from_poll(_poll_fixture())
        for t in topics:
            assert t.source == "abgeordnetenwatch"

    def test_topicless_poll_yields_empty_list(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.polls import topics_from_poll

        topics = topics_from_poll(_topicless_poll())
        assert topics == []

    def test_first_topic_label(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.polls import topics_from_poll

        topics = topics_from_poll(_poll_fixture())
        first = next(t for t in topics if t.topic_id == "aw:gesundheit")
        assert first.label == "Gesundheit"


# ===========================================================================
# Task 2 tests: corpus.py (poll -> SourceItemRecord + chunk_poll)
# ===========================================================================


class TestPollToSourceItemRecord:
    """Tests for corpus.poll_to_source_item_record."""

    def test_external_id_namespaced(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.corpus import (
            poll_to_source_item_record,
        )

        rec = poll_to_source_item_record(_poll_fixture(), bucket="test-bucket")
        assert rec.external_id == "aw_poll:3602"

    def test_source_item_id_is_deterministic(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.corpus import (
            poll_to_source_item_record,
        )

        rec = poll_to_source_item_record(_poll_fixture(), bucket="test-bucket")
        expected = compute_source_item_id("vote_record", "aw_poll:3602")
        assert rec.source_item_id == expected

    def test_req7_id_disjoint_from_bundestag_numeric(self) -> None:
        """Req 7: AW source_item_id != Bundestag numeric id for same poll_id string."""
        aw_id = compute_source_item_id("vote_record", "aw_poll:3602")
        bundestag_id = compute_source_item_id("vote_record", "3602")
        assert aw_id != bundestag_id, (
            "Req 7 violated: AW source_item_id must be disjoint from Bundestag numeric id "
            f"(both resolved to {aw_id})"
        )

    def test_vector_status_is_pending(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.corpus import (
            poll_to_source_item_record,
        )

        rec = poll_to_source_item_record(_poll_fixture(), bucket="test-bucket")
        assert rec.vector_status == "pending"

    def test_authority_tier_is_factual_record(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.corpus import (
            poll_to_source_item_record,
        )

        rec = poll_to_source_item_record(_poll_fixture(), bucket="test-bucket")
        assert rec.authority_tier == AuthorityTier.FACTUAL_RECORD

    def test_source_type_is_vote_record(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.corpus import (
            poll_to_source_item_record,
        )

        rec = poll_to_source_item_record(_poll_fixture(), bucket="test-bucket")
        assert rec.source_type == SourceType.VOTE_RECORD

    def test_party_id_is_all_sentinel(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.corpus import (
            poll_to_source_item_record,
        )

        rec = poll_to_source_item_record(_poll_fixture(), bucket="test-bucket")
        assert rec.party_id == "_all"

    def test_region_and_region_path(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.corpus import (
            poll_to_source_item_record,
        )

        rec = poll_to_source_item_record(_poll_fixture(), bucket="test-bucket")
        assert rec.region == "DE"
        assert rec.region_path == ["EU", "DE"]

    def test_publish_date_parsed(self) -> None:
        from datetime import date

        from src.ingestion.connectors.abgeordnetenwatch.mappers.corpus import (
            poll_to_source_item_record,
        )

        rec = poll_to_source_item_record(_poll_fixture(), bucket="test-bucket")
        assert rec.publish_date == date(2020, 5, 14)

    def test_storage_ref_uses_bucket(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.corpus import (
            poll_to_source_item_record,
        )

        rec = poll_to_source_item_record(_poll_fixture(), bucket="mybucket")
        assert rec.storage_ref == "gs://mybucket/aw_polls/3602.json"

    def test_returns_source_item_record_instance(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.corpus import (
            poll_to_source_item_record,
        )

        rec = poll_to_source_item_record(_poll_fixture(), bucket="test-bucket")
        assert isinstance(rec, SourceItemRecord)


class TestChunkPoll:
    """Tests for corpus.chunk_poll — worker-compatible 2-arg pure function."""

    def _make_source_item(self) -> SourceItemRecord:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.corpus import (
            poll_to_source_item_record,
        )

        return poll_to_source_item_record(_poll_fixture(), bucket="test-bucket")

    def test_chunk_poll_two_arg_signature(self) -> None:
        """chunk_poll MUST accept exactly (source_item, raw) — worker dispatcher contract."""
        from src.ingestion.connectors.abgeordnetenwatch.mappers.corpus import chunk_poll
        import inspect

        sig = inspect.signature(chunk_poll)
        params = list(sig.parameters.keys())
        assert params == ["source_item", "raw"], (
            f"chunk_poll must have signature (source_item, raw), got {params}"
        )

    def test_chunk_poll_returns_one_chunk_per_fraction(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.corpus import chunk_poll

        source_item = self._make_source_item()
        raw = _raw_payload(_make_votes())
        chunks = chunk_poll(source_item, raw)
        # 2 unique fractions in _make_votes() (FDP + SPD; degenerate fraction=[] is skipped)
        assert len(chunks) == 2

    def test_chunk_poll_returns_chunk_record_instances(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.corpus import chunk_poll

        source_item = self._make_source_item()
        raw = _raw_payload(_make_votes())
        chunks = chunk_poll(source_item, raw)
        for c in chunks:
            assert isinstance(c, ChunkRecord)

    def test_chunk_poll_party_ids_resolved_from_raw(self) -> None:
        """Party slugs must come from the raw votes, not an external fraction_map."""
        from src.ingestion.connectors.abgeordnetenwatch.mappers.corpus import chunk_poll

        source_item = self._make_source_item()
        raw = _raw_payload(_make_votes())
        chunks = chunk_poll(source_item, raw)
        party_ids = {c.party_id for c in chunks}
        assert "fdp" in party_ids
        assert "spd" in party_ids

    def test_chunk_poll_copies_region_from_source_item(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.corpus import chunk_poll

        source_item = self._make_source_item()
        raw = _raw_payload(_make_votes())
        chunks = chunk_poll(source_item, raw)
        for c in chunks:
            assert c.region == "DE"

    def test_chunk_poll_copies_authority_tier(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.corpus import chunk_poll

        source_item = self._make_source_item()
        raw = _raw_payload(_make_votes())
        chunks = chunk_poll(source_item, raw)
        for c in chunks:
            assert c.authority_tier == AuthorityTier.FACTUAL_RECORD

    def test_chunk_poll_copies_source_type(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.corpus import chunk_poll

        source_item = self._make_source_item()
        raw = _raw_payload(_make_votes())
        chunks = chunk_poll(source_item, raw)
        for c in chunks:
            assert c.source_type == SourceType.VOTE_RECORD

    def test_chunk_poll_text_is_german_and_nonempty(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.corpus import chunk_poll

        source_item = self._make_source_item()
        raw = _raw_payload(_make_votes())
        chunks = chunk_poll(source_item, raw)
        for c in chunks:
            assert c.text.strip() != ""

    def test_chunk_poll_chunk_keys_unique(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.mappers.corpus import chunk_poll

        source_item = self._make_source_item()
        raw = _raw_payload(_make_votes())
        chunks = chunk_poll(source_item, raw)
        keys = [c.chunk_key for c in chunks]
        assert len(keys) == len(set(keys)), "chunk_keys must be unique"

    def test_chunk_poll_golden_7_fractions(self, aw_poll_3602_poll: dict, aw_poll_3602_votes: dict) -> None:
        """Golden-record: poll 3602 produces exactly 7 ChunkRecords (one per fraction)."""
        from src.ingestion.connectors.abgeordnetenwatch.mappers.corpus import (
            chunk_poll,
            poll_to_source_item_record,
        )

        poll = aw_poll_3602_poll["data"]
        votes = aw_poll_3602_votes["data"]
        source_item = poll_to_source_item_record(poll, bucket="test-bucket")
        raw = {"poll": poll, "votes": votes}
        chunks = chunk_poll(source_item, raw)
        assert len(chunks) == 7, (
            f"Expected 7 fractions (poll 3602 golden fixture), got {len(chunks)}"
        )

    def test_chunk_poll_golden_party_slugs(self, aw_poll_3602_poll: dict, aw_poll_3602_votes: dict) -> None:
        """Golden-record: poll 3602 chunks contain expected canonical party slugs."""
        from src.ingestion.connectors.abgeordnetenwatch.mappers.corpus import (
            chunk_poll,
            poll_to_source_item_record,
        )

        poll = aw_poll_3602_poll["data"]
        votes = aw_poll_3602_votes["data"]
        source_item = poll_to_source_item_record(poll, bucket="test-bucket")
        raw = {"poll": poll, "votes": votes}
        chunks = chunk_poll(source_item, raw)
        party_ids = {c.party_id for c in chunks}
        expected = {"fdp", "spd", "linke", "afd", "cdu", "gruene", "fraktionslos"}
        assert party_ids == expected, (
            f"Expected party_ids {expected}, got {party_ids}"
        )

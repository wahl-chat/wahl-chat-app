# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
get_cursor() unit tests.

Tests the Qdrant max(external_id) cursor query with a mocked QdrantClient.
No live Qdrant required — MagicMock stands in for the client.
"""

from unittest.mock import MagicMock


from src.ingestion.run import get_cursor


def _make_mock_point(external_id_value):
    """Build a minimal mock Qdrant ScoredPoint with a given external_id payload."""
    point = MagicMock()
    point.payload = {"external_id": external_id_value}
    return point


def test_get_cursor_returns_max_external_id():
    """get_cursor() returns external_id from first scroll result."""
    qdrant = MagicMock()
    qdrant.scroll.return_value = ([_make_mock_point(3602)], None)

    result = get_cursor(qdrant, "wahlchat_chunks_dev", "vote_record")

    assert result == 3602, (
        "get_cursor() must return the external_id from the first scroll result."
    )


def test_get_cursor_coerces_digit_string_external_id():
    """a stringified digit external_id is coerced to int."""
    qdrant = MagicMock()
    qdrant.scroll.return_value = ([_make_mock_point("20240115")], None)

    result = get_cursor(qdrant, "wahlchat_chunks_dev", "parliamentary_speech")

    assert result == 20240115 and isinstance(result, int)


def test_get_cursor_returns_none_for_malformed_external_id():
    """a non-numeric / None / bool external_id degrades to None (no under/over-shoot)."""
    for bad in ("not-a-date", "", None, True, 3.5):
        qdrant = MagicMock()
        qdrant.scroll.return_value = ([_make_mock_point(bad)], None)
        result = get_cursor(qdrant, "wahlchat_chunks_dev", "parliamentary_speech")
        assert result is None, f"malformed external_id {bad!r} must yield None"


def test_get_cursor_returns_none_when_no_points():
    """get_cursor() returns None when no points exist for source_type."""
    qdrant = MagicMock()
    qdrant.scroll.return_value = ([], None)

    result = get_cursor(qdrant, "wahlchat_chunks_dev", "vote_record")

    assert result is None, (
        "get_cursor() must return None when scroll returns no points."
    )


def test_get_cursor_passes_source_type_filter():
    """get_cursor() passes source_type in scroll_filter must clause."""

    qdrant = MagicMock()
    qdrant.scroll.return_value = ([_make_mock_point(100)], None)

    get_cursor(qdrant, "wahlchat_chunks_dev", "vote_record")

    call_kwargs = qdrant.scroll.call_args.kwargs
    scroll_filter = call_kwargs.get("scroll_filter")
    assert scroll_filter is not None, "scroll_filter must be passed."
    # Verify the filter contains a source_type MatchValue condition.
    must_conditions = scroll_filter.must
    keys = [c.key for c in must_conditions if hasattr(c, "key")]
    assert "source_type" in keys, "scroll_filter must include a source_type condition."


def test_get_cursor_uses_desc_order_by():
    """get_cursor() passes order_by DESC on external_id."""
    from qdrant_client import models

    qdrant = MagicMock()
    qdrant.scroll.return_value = ([_make_mock_point(999)], None)

    get_cursor(qdrant, "wahlchat_chunks_dev", "vote_record")

    call_kwargs = qdrant.scroll.call_args.kwargs
    order_by = call_kwargs.get("order_by")
    assert order_by is not None, "order_by must be passed to scroll()."
    assert order_by.key == "external_id", "order_by must sort on 'external_id'."
    assert order_by.direction == models.Direction.DESC, (
        "order_by direction must be DESC to retrieve the maximum."
    )

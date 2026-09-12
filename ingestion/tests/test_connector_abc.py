# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
BaseConnector ABC method-set tests.

Asserts that the new 3-method ABC has exactly the right
abstract method set and no longer exposes the 5 removed methods.
"""

import pytest
from ingestion.connector import BaseConnector

# New abstract method set:
_EXPECTED_ABSTRACT_METHODS = {"discover", "fetch", "normalize"}

# Methods that must NOT exist as abstract (were removed):
_REMOVED_METHODS = {
    "read_watermark",
    "write_watermark",
    "store_original",
    "upsert_source_item",
    "enqueue_embed",
}


def test_base_connector_abstract():
    """BaseConnector() raises TypeError — still an ABC."""
    with pytest.raises(TypeError) as exc_info:
        BaseConnector()
    assert "abstract" in str(exc_info.value).lower()


def test_base_connector_abstract_methods():
    """BaseConnector exposes exactly 3 abstract lifecycle methods."""
    actual = set(BaseConnector.__abstractmethods__)
    assert actual == _EXPECTED_ABSTRACT_METHODS, (
        f"BaseConnector must declare exactly 3 abstract methods.\n"
        f"  Expected: {_EXPECTED_ABSTRACT_METHODS}\n"
        f"  Got:      {actual}\n"
        f"  Missing:  {_EXPECTED_ABSTRACT_METHODS - actual}\n"
        f"  Extra:    {actual - _EXPECTED_ABSTRACT_METHODS}"
    )


def test_removed_methods_not_abstract():
    """Removed methods must not be abstract on BaseConnector."""
    still_abstract = _REMOVED_METHODS & set(BaseConnector.__abstractmethods__)
    assert not still_abstract, (
        f"These methods should have been removed from BaseConnector: {still_abstract}"
    )

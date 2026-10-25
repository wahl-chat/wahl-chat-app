# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""PledgeTracker connector package: queue-API client, pledge registry, mapper.

Bespoke bulk runner (Firestore + Qdrant dual-write; not in CONNECTOR_FACTORIES):
``python -m ingestion.connectors.pledgetracker.bulk``.
"""

from ingestion.connectors.pledgetracker.client import (
    PledgeJobFailedError,
    PledgeJobTimeoutError,
    PledgeQueueClient,
    PledgeQueueError,
)
from ingestion.connectors.pledgetracker.connector import PledgeTrackerConnector
from ingestion.connectors.pledgetracker.registry import (
    PledgeInput,
    load_pledge_registry,
)

__all__ = [
    "PledgeInput",
    "PledgeJobFailedError",
    "PledgeJobTimeoutError",
    "PledgeQueueClient",
    "PledgeQueueError",
    "PledgeTrackerConnector",
    "load_pledge_registry",
]

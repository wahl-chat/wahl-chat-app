# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Ingestion connectors package.

Each module in this package is a concrete BaseConnector subclass for one
upstream data source.  Imports are deferred (only triggered by the factory
functions in registry.py) so the package itself has no side effects at
import time.

Exports (append-only — later plans add their own connector registrations):
    bundestag_votes.BundestagVoteConnector  (plan 03-03)
    pledgetracker.PledgeTrackerConnector    (plan 03-05)
"""

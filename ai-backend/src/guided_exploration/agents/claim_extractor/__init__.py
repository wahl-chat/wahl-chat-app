# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Claim extractor agent — extracts concrete positions from party documents."""

from src.guided_exploration.agents.claim_extractor.implementation import (
    ClaimExtractorAgent,
)
from src.guided_exploration.agents.claim_extractor.interface import (
    ClaimExtractorInput,
    ClaimExtractorOutput,
)

__all__ = [
    "ClaimExtractorAgent",
    "ClaimExtractorInput",
    "ClaimExtractorOutput",
]

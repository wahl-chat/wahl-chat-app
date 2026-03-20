# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Custom exceptions for the guided exploration module."""


class GuidedExplorationError(Exception):
    """Base exception for guided exploration module."""

    pass


class SessionNotFoundError(GuidedExplorationError):
    """Session doesn't exist."""

    pass


class AuthorizationError(GuidedExplorationError):
    """User not authorized to access resource."""

    pass


class ExplorationNotFoundError(GuidedExplorationError):
    """Exploration doesn't exist."""

    pass


class InvalidNavigationError(GuidedExplorationError):
    """Invalid navigation path."""

    pass


class ExportGenerationError(GuidedExplorationError):
    """PDF generation failed."""

    pass


class InsufficientChunksError(GuidedExplorationError):
    """Not enough document chunks found to create a meaningful exploration.

    This error is raised when RAG retrieval returns too few chunks for the
    requested parties, indicating the query cannot be answered from the
    available documents.
    """

    def __init__(
        self,
        message: str,
        total_parties: int,
        parties_with_chunks: int,
        parties_without_chunks: list[str],
        available_claims: list | None = None,
    ) -> None:
        super().__init__(message)
        self.total_parties = total_parties
        self.parties_with_chunks = parties_with_chunks
        self.parties_without_chunks = parties_without_chunks
        self.available_claims = available_claims or []

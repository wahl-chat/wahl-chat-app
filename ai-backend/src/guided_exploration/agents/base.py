# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Base interfaces for guided exploration agents."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Generic, TypeVar

from pydantic import BaseModel

from src.guided_exploration.models.streaming import StreamChunk

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class AgentError(Exception):
    """Base exception for agent errors."""

    pass


class AgentExecutionError(AgentError):
    """Error during agent execution."""

    def __init__(self, message: str, agent_name: str, cause: Exception | None = None):
        super().__init__(message)
        self.agent_name = agent_name
        self.cause = cause


class AgentValidationError(AgentError):
    """Error validating agent input or output."""

    def __init__(self, message: str, agent_name: str, field: str | None = None):
        super().__init__(message)
        self.agent_name = agent_name
        self.field = field


class BaseAgent(ABC, Generic[InputT, OutputT]):
    """
    Base interface for non-streaming agents.

    Non-streaming agents process input and return a complete result.
    Used for classification, planning, and knowledge resolution tasks.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique agent identifier."""
        pass

    @abstractmethod
    async def execute(self, input: InputT) -> OutputT:
        """
        Execute agent logic and return result.

        Args:
            input: The typed input for this agent.

        Returns:
            The typed output from this agent.

        Raises:
            AgentExecutionError: If execution fails.
            AgentValidationError: If input/output validation fails.
        """
        pass


class StreamingAgent(ABC, Generic[InputT, OutputT]):
    """
    Interface for streaming agents.

    Streaming agents emit content in chunks, allowing for real-time
    display and progressive rendering. Used for content generation,
    conversation handling, and analysis tasks.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique agent identifier."""
        pass

    @abstractmethod
    def stream(self, input: InputT) -> AsyncIterator[StreamChunk]:
        """
        Stream output chunks.

        Args:
            input: The typed input for this agent.

        Yields:
            StreamChunk objects containing content fragments.
            The final chunk will have is_final=True.

        Raises:
            AgentExecutionError: If streaming fails.
        """
        pass

    @abstractmethod
    async def execute(self, input: InputT) -> OutputT:
        """
        Non-streaming execution returning final output.

        Consumes all stream chunks internally and returns the
        assembled final result. Useful for testing or when
        streaming is not needed.

        Args:
            input: The typed input for this agent.

        Returns:
            The typed output from this agent.

        Raises:
            AgentExecutionError: If execution fails.
        """
        pass

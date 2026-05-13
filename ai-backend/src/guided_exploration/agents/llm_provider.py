# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""LLM provider abstraction for guided exploration agents."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from enum import Enum
from typing import TypeVar

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_openai import OpenAIEmbeddings
from pydantic import BaseModel

from src.utils import safe_load_api_key

T = TypeVar("T", bound=BaseModel)

# Embedding dimension for text-embedding-3-large
EMBEDDING_DIMENSION = 3072


class LLMTier(str, Enum):
    """
    LLM tiers for different use cases.

    Each tier represents a different balance of cost, speed, and capability.
    """

    FAST = "fast"
    """Fast, cheap model for simple classification tasks (e.g., gpt-5.2-mini, gemini-flash-lite)."""

    BALANCED = "balanced"
    """Good balance of quality and cost for most tasks (e.g., gpt-5.2, gemini-flash)."""

    REASONING = "reasoning"
    """High-quality model for complex reasoning tasks (e.g., gpt-5.2, o3)."""


class LLMProvider(ABC):
    """
    Abstraction over LLM calls for testability and flexibility.

    This interface allows agents to make LLM calls without being
    coupled to a specific LLM implementation. Implementations can
    use OpenAI, Anthropic, or any other LLM provider.
    """

    @abstractmethod
    async def generate(
        self,
        messages: list[BaseMessage],
        temperature: float = 0.7,
    ) -> str:
        """
        Generate a text response from the LLM.

        Args:
            messages: The conversation history as LangChain messages.
            temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative).

        Returns:
            The generated text response.
        """
        pass

    @abstractmethod
    async def generate_structured(
        self,
        messages: list[BaseMessage],
        output_schema: type[T],
        temperature: float = 0.0,
    ) -> T:
        """
        Generate a structured response conforming to a Pydantic schema.

        Args:
            messages: The conversation history as LangChain messages.
            output_schema: The Pydantic model class for the output.
            temperature: Sampling temperature (usually 0.0 for structured output).

        Returns:
            An instance of the output_schema populated with LLM response.
        """
        pass

    @abstractmethod
    def stream(
        self,
        messages: list[BaseMessage],
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """
        Stream text response tokens from the LLM.

        Args:
            messages: The conversation history as LangChain messages.
            temperature: Sampling temperature.

        Yields:
            Text chunks as they are generated.
        """
        pass


class LangChainLLMProvider(LLMProvider):
    """
    LangChain-based implementation of LLMProvider.

    Wraps any LangChain BaseChatModel (ChatOpenAI, AzureChatOpenAI, etc.)
    """

    def __init__(self, model: BaseChatModel):
        self._model = model

    async def generate(
        self,
        messages: list[BaseMessage],
        temperature: float = 0.7,
    ) -> str:
        """Generate a text response using the LangChain model."""
        model = self._model.bind(temperature=temperature)
        response = await model.ainvoke(messages)
        return str(response.content)

    async def generate_structured(
        self,
        messages: list[BaseMessage],
        output_schema: type[T],
        temperature: float = 0.0,
    ) -> T:
        """Generate a structured response using LangChain's structured output."""
        model = self._model.bind(temperature=temperature)
        structured_model = model.with_structured_output(output_schema)
        return await structured_model.ainvoke(messages)

    async def stream(
        self,
        messages: list[BaseMessage],
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Stream text response tokens from the LangChain model."""
        model = self._model.bind(temperature=temperature)
        async for chunk in model.astream(messages):
            if chunk.content:
                yield str(chunk.content)


class LLMRegistry:
    """
    Registry for LLM providers organized by tier.

    Allows configuring different LLM providers for different use cases,
    enabling cost optimization and performance tuning.

    Example usage:
        from src.llms import gpt_5_2_mini, gpt_5_2

        registry = LLMRegistry()
        registry.register(LLMTier.FAST, LangChainLLMProvider(gpt_5_2_mini))
        registry.register(LLMTier.BALANCED, LangChainLLMProvider(gpt_5_2))
        registry.register(LLMTier.REASONING, LangChainLLMProvider(gpt_5_2))

        # Get provider for a specific tier
        fast_provider = registry.get(LLMTier.FAST)

        # Get embeddings
        embeddings = registry.embeddings
    """

    def __init__(self) -> None:
        self._providers: dict[LLMTier, LLMProvider] = {}
        self._default_provider: LLMProvider | None = None
        self._embeddings: Embeddings | None = None

    def register(self, tier: LLMTier, provider: LLMProvider) -> "LLMRegistry":
        """
        Register a provider for a specific tier.

        Args:
            tier: The LLM tier to register for.
            provider: The LLM provider to use for this tier.

        Returns:
            Self for method chaining.
        """
        self._providers[tier] = provider
        return self

    def set_default(self, provider: LLMProvider) -> "LLMRegistry":
        """
        Set a default provider to use when a tier is not registered.

        Args:
            provider: The default LLM provider.

        Returns:
            Self for method chaining.
        """
        self._default_provider = provider
        return self

    def get(self, tier: LLMTier) -> LLMProvider:
        """
        Get the provider for a specific tier.

        Falls back to default provider if the tier is not registered.

        Args:
            tier: The LLM tier to get the provider for.

        Returns:
            The LLM provider for the specified tier.

        Raises:
            ValueError: If no provider is registered for the tier and no default is set.
        """
        if tier in self._providers:
            return self._providers[tier]

        if self._default_provider is not None:
            return self._default_provider

        raise ValueError(
            f"No LLM provider registered for tier {tier.value} and no default set"
        )

    @property
    def embeddings(self) -> Embeddings:
        """Get the embeddings model."""
        if self._embeddings is None:
            raise ValueError("No embeddings model configured in registry")
        return self._embeddings

    def set_embeddings(self, embeddings: Embeddings) -> "LLMRegistry":
        """Set the embeddings model."""
        self._embeddings = embeddings
        return self

    @staticmethod
    def create_openai_embeddings() -> Embeddings:
        """Create OpenAI embeddings with text-embedding-3-large."""
        return OpenAIEmbeddings(
            model="text-embedding-3-large",
            openai_api_key=safe_load_api_key("OPENAI_API_KEY"),
        )

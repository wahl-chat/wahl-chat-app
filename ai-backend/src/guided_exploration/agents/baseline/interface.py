# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Interface model for the baseline streaming agent."""

from pydantic import BaseModel, Field


class BaselineInput(BaseModel):
    """Input for streaming a baseline (production-wahl.chat-shaped) reply."""

    query: str = Field(..., description="The original user query")
    rag_context: str = Field(
        ...,
        description="Formatted RAG context with document IDs for citation",
    )
    parties_list: str = Field(
        ...,
        description="Formatted list of relevant parties",
    )
    context_name: str = Field(..., description="Display name of the context")
    conversation_history: str = Field(
        default="",
        description=(
            "Formatted prior conversation (last ~10 turns) so the response "
            "can build on context, resolve back-references, and avoid "
            "repetition."
        ),
    )
    max_claims_per_party: int | None = Field(
        default=None,
        description=(
            "Optional cap on how many claims the baseline assistant may "
            "surface per party in this response. None = no cap (study B "
            "arms); an int = strict cap (study C arms)."
        ),
    )

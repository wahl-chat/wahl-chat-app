# SPDX-FileCopyrightText: 2025 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from typing import Literal

from pydantic import BaseModel, Field


def create_party_list_generator(valid_party_ids: list[str]) -> type[BaseModel]:
    """
    Create a PartyListGenerator model with dynamic party IDs.

    Args:
        valid_party_ids: List of valid party IDs for the current context.

    Returns:
        A Pydantic model class with party_id_list constrained to valid IDs.
    """
    if not valid_party_ids:
        raise ValueError("valid_party_ids must not be empty")

    # Create a Literal type from the valid party IDs
    party_id_literal = Literal[tuple(valid_party_ids)]  # type: ignore[valid-type]

    class DynamicPartyListGenerator(BaseModel):
        """Output of the Party List Generator."""

        party_id_list: list[party_id_literal] = Field(  # type: ignore[valid-type]
            description=f"Liste der Partei-IDs von denen der Nutzer eine Antwort haben will. Gültige Werte: {', '.join(valid_party_ids)}"
        )

    return DynamicPartyListGenerator


class RAG(BaseModel):
    """Output of the RAG Chain."""

    chat_answer: str = Field(
        description="Deine kurze Antwort auf die Nutzerfrage im Markdown-Format mit Hervorhebungen und Absätzen."
    )
    chat_title: str = Field(
        description="Der kurze Titel des Chats in Plain Text. Er soll den Chat kurz und prägnant in 3-5 Worten beschreiben."
    )


class QuickReplyGenerator(BaseModel):
    """Output of the Quick Reply Generator."""

    quick_replies: list[str] = Field(
        description="Liste der drei Quick Replies als Strings."
    )


class QuestionTypeClassifier(BaseModel):
    """Output of the Question Type Classifier."""

    non_party_specific_question: str = Field(
        description="Die Frage die der Nutzer gestellt hat, jedoch in einer Formulierung als ob sie direkt an eine Partei gerichtet ist."
    )
    is_comparing_question: bool = Field(
        description="True, wenn eine explizite Vergleichsfrage, sonst False."
    )


class ChatSummaryGenerator(BaseModel):
    """Output of the Chat Summary Generator."""

    chat_summary: str = Field(
        description="Die wichtigsten Leitfragen die von den Parteien beantwortet wurden."
    )


class GroupChatTitleQuickReplyGenerator(BaseModel):
    """Output of the Chat Title & Quick Reply Generator."""

    chat_title: str = Field(
        description="Ein kurzer Titel, der den Chat kurz und prägnant in 3-5 Worten beschreibt."
    )
    quick_replies: list[str] = Field(
        description="Liste der drei Quick Replies als Strings."
    )


class RerankingOutput(BaseModel):
    """Output of the Reranking Model."""

    reranked_doc_indices: list[int] = Field(
        description="Absteigend nach Nützlichkeit sortierte Liste der Indices der Dokumente"
    )

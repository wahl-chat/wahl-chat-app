# SPDX-FileCopyrightText: 2025 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from src.models.general import LLMSize


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    id: Optional[str] = Field(default=None, description="The unique ID of the message")
    role: Role = Field(..., description="The role of the message author")
    content: str = Field(..., description="The message content")
    sources: Optional[List[dict]] = Field(
        None, description="The sources the message content is based on"
    )
    party_id: Optional[str] = Field(
        default=None, description="The ID of the party the message is coming from"
    )
    current_chat_title: Optional[str] = Field(
        default=None, description="The current chat title"
    )
    quick_replies: Optional[List[str]] = Field(
        default=None, description="Quick replies for the user"
    )
    rag_query: Optional[List[str]] = Field(
        default=None,
        description="The RAG query that was used to fetch background information for the message",
    )


class ChatSession(BaseModel):
    user_id: str = Field(..., description="The Firebase ID of the user")
    party_id: str = Field(
        ..., description="The ID of the party the user is chatting with"
    )
    chat_history: List[Message] = Field(..., description="The chat history")
    title: Optional[str] = Field(None, description="The chat title")
    created_at: Optional[datetime] = Field(
        None, description="The creation date of the chat session"
    )


class ProConAssessment(BaseModel):
    user_id: str = Field(..., description="The Firebase ID of the user")
    party_id: str = Field(
        ..., description="The ID of the party the user is chatting with"
    )
    chat_history: List[Message] = Field(..., description="The chat history")


class GroupChatSession(BaseModel):
    session_id: str = Field(..., description="The ID of the chat session")
    context_id: str = Field(
        ..., description="The ID of the context (e.g., 'bundestagswahl-2025')"
    )
    chat_history: List[Message] = Field(..., description="The chat history")
    title: Optional[str] = Field(None, description="The chat title")
    chat_response_llm_size: LLMSize = Field(
        ..., description="The LLM size for the chat response"
    )
    last_quick_replies: List[str] = Field(
        description="The last quick replies for the user", default=[]
    )
    is_cacheable: bool = Field(
        description="Whether the chat history is cacheable or not", default=True
    )


class CachedResponse(BaseModel):
    content: str = Field(..., description="The content of the cached response")
    sources: Optional[List[dict]] = Field(
        None, description="The sources the message content is based on"
    )
    created_at: datetime = Field(
        ..., description="The creation date of the cached response"
    )
    rag_query: Optional[List[str]] = Field(
        None,
        description="The RAG query that was used to fetch background information for the message",
    )
    cached_conversation_history: Optional[str] = Field(
        None,
        description="The cached conversation history string for which the response was generated",
    )
    depth: Optional[int] = Field(
        None,
        description="The number of messages in the conversation history for which the response was generated",
    )
    user_message_depth: Optional[int] = Field(
        None,
        description="The number of user messages in the conversation history for which the response was generated",
    )

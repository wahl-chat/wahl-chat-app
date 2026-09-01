# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import enum
from pydantic import BaseModel, Field, field_validator, ValidationError
from typing import List, Optional

from src.models.vote import Vote
from .chat import Message
from .context import ContextParty

# ---------------------------------------------------------------------------
# Input bounds for PUBLIC (unauthenticated) request DTOs. Every field flows
# into LLM prompts, so an unbounded body is a cost / context-overflow / memory
# vector; Pydantic rejects oversized input with 422 BEFORE any retrieval or
# provider call. Sized far above real usage — abuse guards, not UX limits.
# Pydantic validates only after the body is parsed, so a raw request-body cap
# at the proxy / ASGI edge is still required in deployment.
# ---------------------------------------------------------------------------
MAX_ID_CHARS = 128
MAX_USER_MESSAGE_CHARS = 4_000
MAX_ASSISTANT_MESSAGE_CHARS = 40_000
MAX_HISTORY_MESSAGES = 100


class CreateSessionRequest(BaseModel):
    party_id: str = Field(
        ..., description="The ID of the party the user is chatting with"
    )
    user_id: str = Field(..., description="The ID of the user")


class ChatAnswerRequest(BaseModel):
    user_id: str = Field(..., description="The ID of the user")
    chat_session_id: str = Field(..., description="The ID of the chat session")
    user_message: str = Field(..., description="The user message to answer")


class GroupChatDto(BaseModel):
    chat_history: List[Message] = Field(..., description="The chat history")
    pre_selected_parties: List[ContextParty] = Field(
        ..., description="The pre selected parties"
    )


class GroupChatResponseDto(BaseModel):
    new_messages: List[Message] = Field(..., description="The chat history")
    current_chat_title: str = Field(..., description="The current chat title")
    quick_replies: List[str] = Field(..., description="The quick replies")


class StatusIndicator(str, enum.Enum):
    ERROR = "error"
    SUCCESS = "success"


class Status(BaseModel):
    indicator: StatusIndicator = Field(..., description="The status of the event")
    message: str = Field(..., description="The message")


class InitChatSessionDto(BaseModel):
    session_id: str = Field(..., description="The ID of the chat session")
    chat_history: List[Message] = Field(..., description="The chat history")
    current_title: str = Field(..., description="The current chat title")
    last_quick_replies: List[str] = Field(
        description="The last quick replies that were shown to the user", default=[]
    )
    is_cacheable: bool = Field(
        description="Whether the chat history is cacheable or not", default=True
    )
    context_id: Optional[str] = Field(
        default=None,
        description="The ID of the context (e.g., 'bundestagswahl-2025'). Defaults to the default context if not provided.",
    )


class ChatSessionInitializedDto(BaseModel):
    session_id: Optional[str] = Field(
        ..., description="The ID of the chat session if applicable"
    )
    status: Status = Field(..., description="The status of the event")


class ProConPerspectiveRequestDto(BaseModel):
    request_id: str = Field(
        ...,
        max_length=MAX_ID_CHARS,
        description="The ID of the Pro/Con assessment request",
    )
    party_id: str = Field(
        ...,
        max_length=MAX_ID_CHARS,
        description="The ID of the party the user is chatting with",
    )
    last_user_message: str = Field(
        ..., max_length=MAX_USER_MESSAGE_CHARS, description="The last user message"
    )
    last_assistant_message: str = Field(
        ...,
        max_length=MAX_ASSISTANT_MESSAGE_CHARS,
        description="The last assistant message",
    )
    context_id: Optional[str] = Field(
        None,
        max_length=MAX_ID_CHARS,
        description="The context ID for the political context (e.g., election)",
    )


class ProConPerspectiveDto(BaseModel):
    request_id: Optional[str] = Field(
        ..., description="The ID of the Pro/Con assessment request if applicable"
    )
    message: Optional[Message] = Field(
        default=None, description="The Pro/Con assessment message"
    )
    status: Status = Field(..., description="The status of the event")


class VotingBehaviorRequestDto(BaseModel):
    request_id: str = Field(
        ...,
        max_length=MAX_ID_CHARS,
        description="The ID of the voting behavior request",
    )
    party_id: str = Field(
        ...,
        max_length=MAX_ID_CHARS,
        description="The ID of the party the user is chatting with",
    )
    context_id: Optional[str] = Field(
        default=None,
        max_length=MAX_ID_CHARS,
        description="Election context id; scopes party lookup and vote retrieval.",
    )
    last_user_message: str = Field(
        ..., max_length=MAX_USER_MESSAGE_CHARS, description="The last user message"
    )
    last_assistant_message: str = Field(
        ...,
        max_length=MAX_ASSISTANT_MESSAGE_CHARS,
        description="The last assistant message",
    )


class ParliamentaryQuestionRequestDto(BaseModel):
    request_id: str = Field(
        ...,
        max_length=MAX_ID_CHARS,
        description="The ID of the parliamentary question request",
    )
    party_id: str = Field(
        ...,
        max_length=MAX_ID_CHARS,
        description="The ID of the party the user is chatting with",
    )
    last_user_message: str = Field(
        ..., max_length=MAX_USER_MESSAGE_CHARS, description="The last user message"
    )
    last_assistant_message: str = Field(
        ...,
        max_length=MAX_ASSISTANT_MESSAGE_CHARS,
        description="The last assistant message",
    )


class VotingBehaviorVoteDto(BaseModel):
    request_id: str = Field(..., description="The ID of the voting behavior request")
    vote: Vote = Field(..., description="The vote")


class VotingBehaviorSummaryChunkDto(BaseModel):
    request_id: str = Field(..., description="The ID of the voting behavior request")
    chunk_index: int = Field(..., description="The index of the chunk in the summary")
    summary_chunk: str = Field(..., description="The message content")
    is_end: bool = Field(
        ..., description="Whether this is the last chunk of the summary"
    )


class VotingBehaviorDto(BaseModel):
    request_id: Optional[str] = Field(
        ..., description="The ID of the voting behavior request if applicable"
    )
    message: str = Field(..., description="The voting behavior message")
    status: Status = Field(..., description="The status of the event")
    votes: list[Vote] = Field(..., description="The votes")
    rag_query: Optional[str] = Field(
        ..., description="The RAG query that was used to get the votes"
    )


class ParliamentaryQuestionDto(BaseModel):
    request_id: Optional[str] = Field(
        ..., description="The ID of the parliamentary question request if applicable"
    )
    status: Status = Field(..., description="The status of the event")
    parliamentary_questions: list[Vote] = Field(
        ..., description="The parliamentary questions"
    )
    rag_query: Optional[str] = Field(
        ..., description="The RAG query that was used to get the votes"
    )


class ChatUserMessageDto(BaseModel):
    id: Optional[str] = Field(
        default=None, description="The ID of the chat user message"
    )
    session_id: str = Field(
        ..., description="The ID of the chat session to which the message belongs"
    )
    user_message: str = Field(
        default="", description="The user message to answer", max_length=500
    )
    party_ids: List[str] = Field(
        ..., description="The IDs of the parties that are part of the chat session"
    )
    # Optional audio fields for voice messages
    audio_bytes: Optional[bytes] = Field(
        default=None, description="Raw binary audio data (webm) for voice messages"
    )
    grouped_message_id: Optional[str] = Field(
        default=None,
        description="The ID of the grouped message (document id) for voice messages",
    )
    language: str = Field(
        default="de", description="Language code for transcription (ISO-639-1)"
    )

    @field_validator("session_id")
    def session_id_must_not_be_empty(cls, value):
        if not value.strip():  # Check for empty or whitespace-only strings
            raise ValidationError("Session ID cannot be empty or whitespace.")
        return value


class TitleDto(BaseModel):
    session_id: str = Field(..., description="The ID of the chat session to update")
    title: str = Field(..., description="The new title of the chat session")


class SourcesDto(BaseModel):
    session_id: str = Field(
        ..., description="The ID of the chat session which the sources belong to"
    )
    sources: List[dict] = Field(
        ..., description="The sources for the response that will be generated"
    )
    party_id: Optional[str] = Field(
        ...,
        description="The ID of the party for which the sources were retrieved. None for general Perplexity chat",
    )
    rag_query: Optional[List[str]] = Field(
        ..., description="The RAG query that was used to get the sources if any"
    )


class RespondingPartiesDto(BaseModel):
    session_id: str = Field(
        ..., description="The ID of the chat session to which the message belongs"
    )
    party_ids: List[str] = Field(
        ..., description="The IDs of the parties that are responding"
    )


class PartyResponseChunkDto(BaseModel):
    session_id: str = Field(
        ..., description="The ID of the chat session to which the message belongs"
    )
    party_id: Optional[str] = Field(
        ...,
        description="The ID of the party the message is coming from. None for general Perplexity chat",
    )
    chunk_index: int = Field(..., description="The index of the chunk in the response")
    chunk_content: str = Field(..., description="The message content")
    is_end: bool = Field(
        ..., description="Whether this is the last chunk of the response"
    )


class PartyResponseCompleteDto(BaseModel):
    session_id: str = Field(
        ..., description="The ID of the chat session to which the message belongs"
    )
    party_id: Optional[str] = Field(
        ...,
        description="The ID of the party the message is coming from. None for general perplexity",
    )
    complete_message: str = Field(..., description="The complete message content")
    message_id: Optional[str] = Field(
        default=None, description="The unique ID of the assistant message"
    )
    status: Status = Field(..., description="The status of the event")


class ChatResponseCompleteDto(BaseModel):
    session_id: Optional[str] = Field(
        ...,
        description="The ID of the chat session to which the message belongs if applicable",
    )
    status: Status = Field(..., description="The status of the event")


class WahlChatSwiperUserMessageDto(BaseModel):
    session_id: str = Field(
        ..., description="The ID of the chat session to which the message belongs"
    )
    user_message: str = Field(
        ..., description="The user message to answer", max_length=500
    )
    current_political_question: str = Field(
        ...,
        description="The current wahl.chat Swiper question which the user is answering",
    )

    @field_validator("session_id")
    def session_id_must_not_be_empty(cls, value):
        if not value.strip():  # Check for empty or whitespace-only strings
            raise ValidationError("Session ID cannot be empty or whitespace.")
        return value


class WahlChatSwiperResponseCompleteDto(BaseModel):
    session_id: Optional[str] = Field(
        ...,
        description="The ID of the chat session to which the message belongs if applicable",
    )
    complete_message: Message = Field(..., description="The message including sources")
    status: Status = Field(..., description="The status of the event")


class QuickRepliesAndTitleDto(BaseModel):
    session_id: str = Field(
        ..., description="The ID of the chat session to which the message belongs"
    )
    quick_replies: List[str] = Field(..., description="The quick replies for the user")
    title: str = Field(..., description="The new title of the chat session")


class RequestSummaryDto(BaseModel):
    chat_history: List[Message] = Field(
        ..., max_length=MAX_HISTORY_MESSAGES, description="The chat history"
    )


class SummaryDto(BaseModel):
    chat_summary: str = Field(..., description="The chat summary")
    status: Status = Field(..., description="The status of the event")


class WahlChatSwiperAnswerRequestDto(BaseModel):
    chat_history: List[Message] = Field(
        ..., max_length=MAX_HISTORY_MESSAGES, description="The chat history"
    )
    current_title: str = Field(
        ..., max_length=500, description="The current chat title"
    )
    user_message: str = Field(
        ..., description="The user message to answer", max_length=500
    )
    current_political_question: str = Field(
        ...,
        max_length=1_000,
        description="The current wahl.chat Swiper question which the user is answering",
    )


class WahlChatSwiperAnswerDto(BaseModel):
    message: Message = Field(..., description="The message including sources")
    title: str = Field(..., description="The new title of the chat session")
    quick_replies: List[str] = Field(..., description="The quick replies for the user")


# Voice-related DTOs


class VoiceTranscribedDto(BaseModel):
    session_id: str = Field(..., description="The ID of the chat session")
    grouped_message_id: str = Field(
        ..., description="Wrapper ID to correlate request with response"
    )
    message_id: Optional[str] = Field(
        default=None, description="Inner ID to correlate request with response"
    )
    transcribed_text: str = Field(..., description="The transcribed text from audio")

# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""All SSE event types for guided exploration."""

from typing import Literal, Union

from pydantic import BaseModel, Field

from src.guided_exploration.models.content import Analysis, Citation
from src.guided_exploration.models.conversation import Conversation, Message
from src.guided_exploration.models.navigation import NavigationState, SiblingNavigation
from src.guided_exploration.models.tree import Subtopic, TopicTree


class ConnectedEvent(BaseModel):
    """Sent when SSE connection is established."""

    type: Literal["connected"] = "connected"
    session_id: str = Field(..., description="The connected session ID")


class ThinkingEvent(BaseModel):
    """Sent to indicate processing stage."""

    type: Literal["thinking"] = "thinking"
    stage: Literal["classifying", "planning", "retrieving", "generating"] = Field(
        ..., description="Current processing stage"
    )
    message: str = Field(..., description="Human-readable status message")


class ChoicePromptEvent(BaseModel):
    """Sent when user needs to choose exploration vs quick answer."""

    type: Literal["choice_prompt"] = "choice_prompt"
    query_id: str = Field(..., description="ID for tracking this query")
    original_query: str = Field(..., description="The user's original query")
    options: list[dict] = Field(
        ..., description="Available options for the user to choose"
    )


class TopicTreeEvent(BaseModel):
    """Sent when topic tree is generated (after Phase 2, before knowledge resolution)."""

    type: Literal["topic_tree"] = "topic_tree"
    exploration_id: str = Field(..., description="ID of the new exploration")
    tree: TopicTree = Field(..., description="The generated topic tree")
    navigation: NavigationState = Field(..., description="Current navigation state")


class ExplorationReadyEvent(BaseModel):
    """Sent when exploration is fully ready (knowledge base loaded after Phase 4)."""

    type: Literal["exploration_ready"] = "exploration_ready"
    exploration_id: str = Field(..., description="ID of the exploration")
    topics_count: int = Field(..., description="Number of topics in the tree")
    subtopics_count: int = Field(..., description="Number of subtopics with knowledge")
    parties_count: int = Field(
        ..., description="Number of parties with resolved knowledge"
    )


class TopicOverviewEvent(BaseModel):
    """Sent when navigating to a topic."""

    type: Literal["topic_overview"] = "topic_overview"
    topic_id: str = Field(..., description="ID of the topic")
    name: str = Field(..., description="Display name of the topic")
    description: str = Field(..., description="Topic description")
    subtopics: list[Subtopic] = Field(..., description="Subtopics under this topic")
    navigation: NavigationState = Field(..., description="Current navigation state")


class ConversationOpenedEvent(BaseModel):
    """Sent when navigating to a leaf node."""

    type: Literal["conversation_opened"] = "conversation_opened"
    leaf_id: str = Field(..., description="ID of the leaf node")
    conversation: Conversation = Field(
        ..., description="The conversation for this leaf"
    )
    navigation: NavigationState = Field(..., description="Current navigation state")
    analysis_available: bool = Field(
        ..., description="Whether analysis can be requested"
    )
    sibling_navigation: SiblingNavigation = Field(
        ..., description="Previous/next sibling info"
    )
    suggested_questions: list[str] = Field(
        default_factory=list, description="Suggested follow-up questions for this topic"
    )


class ConversationMessageEvent(BaseModel):
    """Sent when a new message is added to conversation."""

    type: Literal["conversation_message"] = "conversation_message"
    leaf_id: str = Field(..., description="ID of the leaf node")
    message: Message = Field(..., description="The new message")
    navigation: NavigationState | None = Field(
        default=None, description="Updated navigation state if changed"
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="Citations used in the message (for lookup by frontend)",
    )
    suggested_questions: list[str] = Field(
        default_factory=list,
        description="Suggested follow-up questions for the user",
    )


class StreamChunkEvent(BaseModel):
    """Sent for streaming content chunks."""

    type: Literal["stream_chunk"] = "stream_chunk"
    stream_id: str = Field(..., description="ID to correlate chunks")
    target_type: Literal[
        "initial_content", "followup", "analysis", "quick_summary", "system_message"
    ] = Field(..., description="What is being streamed")
    target_id: str = Field(..., description="ID of the target (leaf_id, query_id, etc)")
    section: str | None = Field(
        default=None, description="Section within structured content"
    )
    chunk: str = Field(..., description="The content chunk")
    chunk_index: int = Field(..., description="Index of this chunk in the stream")


class StreamEndEvent(BaseModel):
    """Sent when streaming completes."""

    type: Literal["stream_end"] = "stream_end"
    stream_id: str = Field(..., description="ID of the completed stream")
    target_type: str = Field(..., description="What was being streamed")
    target_id: str = Field(..., description="ID of the target")
    complete: bool = Field(..., description="Whether stream completed successfully")


class QuickSummaryEvent(BaseModel):
    """Sent for quick factual queries."""

    type: Literal["quick_summary"] = "quick_summary"
    query_id: str = Field(..., description="ID of the query")
    original_query: str = Field(..., description="The user's query")
    text: str = Field(..., description="The full response text with inline citations")
    citations: list[Citation] = Field(
        default_factory=list, description="Citations for the summary"
    )
    can_explore_deeper: bool = Field(
        ..., description="Whether deeper exploration is available"
    )
    suggested_questions: list[str] = Field(
        default_factory=list, description="Suggested follow-up questions for the user"
    )


class AnalysisResultEvent(BaseModel):
    """Sent when analysis is generated."""

    type: Literal["analysis_result"] = "analysis_result"
    leaf_id: str = Field(..., description="ID of the analyzed leaf")
    analysis: Analysis = Field(..., description="The generated analysis")


class SummaryGeneratingEvent(BaseModel):
    """Sent during summary generation."""

    type: Literal["summary_generating"] = "summary_generating"
    leaf_id: str = Field(..., description="ID of the leaf being summarized")
    status: Literal["started", "completed", "failed"] = Field(
        ..., description="Status of summary generation"
    )
    error: str | None = Field(default=None, description="Error message if failed")


class ExplorationCompleteEvent(BaseModel):
    """Sent when exploration is completed."""

    type: Literal["exploration_complete"] = "exploration_complete"
    exploration_id: str = Field(..., description="ID of the completed exploration")
    closing_summary: str = Field(..., description="Final summary text")
    stats: dict = Field(..., description="Statistics about the exploration")
    next_actions: dict = Field(..., description="Suggested next actions")
    unexplored_topics: list[dict] = Field(
        ..., description="Topics that were not explored"
    )


class ExportReadyEvent(BaseModel):
    """Sent when PDF export is ready."""

    type: Literal["export_ready"] = "export_ready"
    exploration_id: str = Field(..., description="ID of the exported exploration")
    export_id: str = Field(..., description="ID of the export")
    download_url: str = Field(..., description="URL to download the PDF")
    expires_at: str = Field(..., description="When the download URL expires")
    filename: str = Field(..., description="Suggested filename")


class ChatMessageEvent(BaseModel):
    """Sent for regular chat messages (quick factual answers)."""

    type: Literal["chat_message"] = "chat_message"
    message_id: str = Field(..., description="ID of the message")
    content: str = Field(..., description="The message content")
    citations: list[Citation] = Field(
        default_factory=list, description="Citations for the answer"
    )
    can_explore_deeper: bool = Field(
        default=False, description="Whether exploration option is available"
    )
    query_id: str | None = Field(
        default=None, description="Set if user can still choose to explore"
    )
    suggested_questions: list[str] = Field(
        default_factory=list, description="Suggested follow-up questions for the user"
    )


class ErrorEvent(BaseModel):
    """Sent when an error occurs."""

    type: Literal["error"] = "error"
    code: str = Field(..., description="Error code for client handling")
    message: str = Field(..., description="Human-readable error message")
    recoverable: bool = Field(..., description="Whether the error is recoverable")
    suggested_action: str | None = Field(
        default=None, description="Suggested action for the user"
    )


class ReconnectedEvent(BaseModel):
    """Sent when reconnecting to an existing session."""

    type: Literal["reconnected"] = "reconnected"
    session_id: str = Field(..., description="The reconnected session ID")
    active_exploration: dict | None = Field(
        default=None, description="Active exploration state if any"
    )
    resuming_stream: dict | None = Field(
        default=None, description="Stream being resumed if any"
    )


class SessionClaimedEvent(BaseModel):
    """Sent when session is claimed by authenticated user."""

    type: Literal["session_claimed"] = "session_claimed"
    session_id: str = Field(..., description="The claimed session ID")
    message: str = Field(..., description="Confirmation message")


# Union type for all SSE events
SSEEvent = Union[
    ConnectedEvent,
    ThinkingEvent,
    ChoicePromptEvent,
    TopicTreeEvent,
    ExplorationReadyEvent,
    TopicOverviewEvent,
    ConversationOpenedEvent,
    ConversationMessageEvent,
    StreamChunkEvent,
    StreamEndEvent,
    QuickSummaryEvent,
    ChatMessageEvent,
    AnalysisResultEvent,
    SummaryGeneratingEvent,
    ExplorationCompleteEvent,
    ExportReadyEvent,
    ErrorEvent,
    ReconnectedEvent,
    SessionClaimedEvent,
]

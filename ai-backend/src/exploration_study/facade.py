"""Facade for exploration study - public module interface."""

import logging
from datetime import datetime
from typing import Literal

from src.exploration_study.services.quiz_generator import (
    create_quiz_generator_service,
)
from src.exploration_study.services.session_repository import (
    SessionRepository,
    get_session_repository,
)
from src.guided_exploration.agents.llm_provider import (
    LLMRegistry,
    LLMTier,
    LangChainLLMProvider,
)
from src.llms import openai_gpt_5_4

logger = logging.getLogger(__name__)


class ExplorationStudyFacade:
    """
    Public interface for exploration study module.

    Coordinates between study sessions, quiz generation, and the
    guided exploration module.
    """

    def __init__(
        self,
        session_repository: SessionRepository,
        llm_registry: LLMRegistry,
    ) -> None:
        self._session_repo = session_repository
        self._llm_registry = llm_registry
        self._quiz_generator = create_quiz_generator_service(
            llm_provider=llm_registry.get(LLMTier.REASONING)
        )

    async def create_exploration_session(
        self,
        context_id: str,
        mode: Literal["guided", "baseline"] = "guided",
    ) -> dict:
        """
        Create a guided exploration session for a study task.

        Args:
            context_id: The context ID (e.g., "study-fake-parties")
            mode: "guided" for full exploration, "baseline" for summary-only

        Returns:
            Dict with session_id and stream_url
        """
        # Import here to avoid circular imports
        from src.guided_exploration.facade import get_facade as get_ge_facade
        from src.guided_exploration.models import SessionMode

        ge_facade = get_ge_facade()

        # Map mode string to SessionMode enum
        session_mode = SessionMode.GUIDED if mode == "guided" else SessionMode.BASELINE

        # Create session via guided exploration facade with mode
        session_info = await ge_facade.create_session(
            context_id=context_id,
            user_id=None,  # Study sessions don't have user auth
            mode=session_mode,
        )

        logger.info(
            f"Created exploration session {session_info.session_id} "
            f"with mode={mode} for context={context_id}"
        )

        return {
            "session_id": session_info.session_id,
            "stream_url": session_info.stream_url,
            "mode": mode,
        }

    async def start_quiz_generation(
        self,
        session_id: str,
        topic: str,
        parties: list[str],
        chat_id: str,
    ) -> None:
        """
        Start asynchronous quiz generation for a completed task.

        Args:
            session_id: The study session ID
            topic: The topic explored
            parties: List of party names
            chat_id: The guided exploration session ID

        Raises:
            ValueError: If no chat messages are found for the chat_id
        """
        # Get chat history from guided exploration
        chat_messages = await self._get_chat_messages(chat_id)

        if not chat_messages:
            raise ValueError(
                f"No chat messages found for chat_id={chat_id}. "
                f"Cannot generate quiz without conversation history."
            )

        # Size the quiz to the participant's actual exposure: ~0.6 questions
        # per position encountered, clamped to [5, 12]. Scoring is deferred
        # to analysis time (see questionnaire-plan.md §Page 7).
        study_session = await self._session_repo.get_session(session_id)
        visited_count = (
            len(study_session.condition.positions_encountered)
            if study_session and study_session.condition
            else 0
        )
        num_questions = max(5, min(12, int(visited_count * 0.6)))

        # Start quiz generation in background
        self._quiz_generator.start_quiz_generation(
            session_id=session_id,
            topic=topic,
            parties=parties,
            chat_messages=chat_messages,
            num_questions=num_questions,
        )

        logger.info(
            f"Started quiz generation for session={session_id} "
            f"(visited={visited_count}, num_questions={num_questions})"
        )

    async def _get_chat_messages(self, chat_id: str) -> list[dict]:
        """
        Get chat messages from a guided exploration session.

        Extracts all messages from:
        1. Session-level messages (quick summaries, baseline responses)
        2. Exploration leaf conversations (follow-up messages)

        Returns messages in chronological order for quiz generation.
        """
        from src.guided_exploration.facade import get_facade as get_ge_facade

        ge_facade = get_ge_facade()
        session_data = await ge_facade.get_session(chat_id)

        if not session_data:
            return []

        messages = []

        # 1. Get session-level messages (quick summaries, baseline responses)
        session_messages = session_data.get("messages", [])
        for msg in session_messages:
            msg_type = msg.get("type")
            content = msg.get("content")

            # Map session message types to roles
            if msg_type == "user":
                role = "user"
            elif msg_type == "assistant":
                role = "assistant"
            else:
                # Skip exploration_start and other non-chat messages
                continue

            if content:
                messages.append(
                    {
                        "role": role,
                        "content": content,
                        "timestamp": msg.get("timestamp"),
                    }
                )

        # 2. Get messages from all exploration conversations
        explorations = session_data.get("explorations", [])
        for exp in explorations:
            exploration_id = exp.id if hasattr(exp, "id") else exp.get("id")
            if not exploration_id:
                continue

            # Get all conversations for this exploration
            conversations = await ge_facade.get_exploration_conversations(
                chat_id, exploration_id
            )

            for conversation in conversations:
                conv_messages = (
                    conversation.messages
                    if hasattr(conversation, "messages")
                    else conversation.get("messages", [])
                )
                for msg in conv_messages:
                    # Extract role and content from message
                    role = msg.role if hasattr(msg, "role") else msg.get("role")
                    content = (
                        msg.content if hasattr(msg, "content") else msg.get("content")
                    )
                    timestamp = (
                        msg.timestamp
                        if hasattr(msg, "timestamp")
                        else msg.get("timestamp")
                    )

                    # Handle MessageRole enum
                    if hasattr(role, "value"):
                        role = role.value

                    # Handle content that might be a complex object
                    if hasattr(content, "summary"):
                        # SubtopicContent - extract the summary
                        content_text = content.summary
                    elif isinstance(content, dict) and "summary" in content:
                        content_text = content["summary"]
                    elif isinstance(content, str):
                        content_text = content
                    else:
                        continue

                    if role in ("user", "assistant") and content_text:
                        messages.append(
                            {
                                "role": role,
                                "content": content_text,
                                "timestamp": timestamp,
                            }
                        )

        # Sort by timestamp if available, then remove timestamp field
        # Normalize timestamps: convert strings to datetime, use datetime.min as fallback
        def normalize_timestamp(ts):
            if ts is None:
                return datetime.min
            if isinstance(ts, datetime):
                return ts
            if isinstance(ts, str):
                try:
                    # Try ISO format first
                    return datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except ValueError:
                    return datetime.min
            return datetime.min

        messages.sort(key=lambda m: normalize_timestamp(m.get("timestamp")))
        for msg in messages:
            msg.pop("timestamp", None)

        return messages


# Singleton instance
_facade: ExplorationStudyFacade | None = None


def get_facade() -> ExplorationStudyFacade:
    """Get or create the global exploration study facade."""
    global _facade
    if _facade is None:
        session_repository = get_session_repository()

        # Quiz generation runs on the REASONING tier — verbatim source
        # citation + overlap detection benefit from a stronger model.
        registry = LLMRegistry()
        registry.register(LLMTier.REASONING, LangChainLLMProvider(openai_gpt_5_4))

        _facade = ExplorationStudyFacade(session_repository, registry)

        # Register the Information Exposure logger on the guided exploration
        # facade. This crosses the module boundary via callback injection so
        # guided_exploration has no hard dependency on exploration_study.
        from src.exploration_study.services.exposure_logger import (
            log_study_exposure,
        )
        from src.guided_exploration.facade import get_facade as get_ge_facade

        try:
            get_ge_facade().set_study_exposure_logger(log_study_exposure)
        except Exception as e:
            logger.warning(f"Could not register study exposure logger: {e}")
    return _facade

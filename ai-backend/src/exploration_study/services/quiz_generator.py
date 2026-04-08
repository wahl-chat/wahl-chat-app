"""Quiz generation service."""

import asyncio
import logging
from datetime import datetime, timezone

from src.exploration_study.agents.quiz_generator import (
    QuizGeneratorAgent,
    QuizGeneratorInput,
)
from src.exploration_study.agents.quiz_generator.interface import ChatMessage
from src.exploration_study.models.quiz import Quiz, QuizStatus
from src.exploration_study.services.session_repository import (
    SessionRepository,
    get_session_repository,
)
from src.guided_exploration.agents.llm_provider import LLMProvider

logger = logging.getLogger(__name__)


class QuizGeneratorService:
    """
    Service for generating quizzes asynchronously.

    This service:
    1. Fetches chat history from the guided exploration session
    2. Uses the quiz generator agent to create questions
    3. Updates the quiz in the database
    """

    def __init__(
        self,
        session_repository: SessionRepository,
        llm_provider: LLMProvider,
    ) -> None:
        self._session_repo = session_repository
        self._agent = QuizGeneratorAgent(llm_provider)

    async def generate_quiz_async(
        self,
        session_id: str,
        topic: str,
        parties: list[str],
        chat_messages: list[dict],
    ) -> None:
        """
        Generate a quiz asynchronously.

        This method is designed to be called with asyncio.create_task()
        so it runs in the background while the participant continues.
        """
        quiz: Quiz | None = None
        try:
            # Create or get the quiz record
            quiz = await self._session_repo.get_session_quiz(session_id)
            if not quiz:
                quiz = await self._session_repo.create_quiz(session_id)

            # Update status to generating
            await self._session_repo.update_quiz(
                session_id,
                quiz.id,
                {"status": QuizStatus.GENERATING.value},
            )

            # Convert chat messages to the expected format
            formatted_messages = [
                ChatMessage(
                    role=msg.get("role", "user"),
                    content=msg.get("content", ""),
                )
                for msg in chat_messages
                if msg.get("content")
            ]

            # Generate questions using the agent
            agent_input = QuizGeneratorInput(
                topic=topic,
                parties=parties,
                chat_messages=formatted_messages,
                num_questions=10,
            )

            output = await self._agent.execute(agent_input)

            # Convert to QuizQuestion models
            questions = self._agent.convert_to_quiz_questions(output, topic)

            # Update quiz with generated questions
            await self._session_repo.update_quiz(
                session_id,
                quiz.id,
                {
                    "status": QuizStatus.READY.value,
                    "questions": [q.model_dump(mode="json") for q in questions],
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                },
            )

            logger.info(
                f"Quiz generation complete for session {session_id}: "
                f"{len(questions)} questions"
            )

        except Exception as e:
            logger.exception(
                f"Quiz generation failed for session {session_id}: {e}"
            )
            # Update quiz with error status
            if quiz:
                await self._session_repo.update_quiz(
                    session_id,
                    quiz.id,
                    {
                        "status": QuizStatus.FAILED.value,
                        "error_message": str(e),
                    },
                )

    def start_quiz_generation(
        self,
        session_id: str,
        topic: str,
        parties: list[str],
        chat_messages: list[dict],
    ) -> asyncio.Task:
        """
        Start quiz generation in the background.

        Returns the task so the caller can optionally await it.
        """
        return asyncio.create_task(
            self.generate_quiz_async(
                session_id=session_id,
                topic=topic,
                parties=parties,
                chat_messages=chat_messages,
            )
        )


# Factory function (facade will provide the LLM provider)
def create_quiz_generator_service(
    llm_provider: LLMProvider,
) -> QuizGeneratorService:
    """Create a quiz generator service with the given LLM provider."""
    return QuizGeneratorService(
        session_repository=get_session_repository(),
        llm_provider=llm_provider,
    )

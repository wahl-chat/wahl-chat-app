"""Implementation of quiz generator agent."""

import logging
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage

from src.guided_exploration.agents.base import BaseAgent
from src.guided_exploration.agents.llm_provider import LLMProvider
from src.exploration_study.agents.quiz_generator.interface import (
    QuizGeneratorInput,
    QuizGeneratorOutput,
)
from src.exploration_study.agents.quiz_generator.prompts import (
    GENERATION_PROMPT,
    SYSTEM_PROMPT,
    format_chat_history,
    format_parties,
)
from src.exploration_study.models.quiz import QuizQuestion

logger = logging.getLogger(__name__)


class QuizGeneratorAgent(BaseAgent[QuizGeneratorInput, QuizGeneratorOutput]):
    """
    Generates multiple-choice quiz questions from chat history.

    Takes the chat messages from an exploration session and generates
    questions that test retention of the party positions discussed.
    """

    def __init__(self, llm_provider: LLMProvider):
        self._llm = llm_provider

    @property
    def name(self) -> str:
        return "quiz_generator"

    async def execute(self, input: QuizGeneratorInput) -> QuizGeneratorOutput:
        """Generate quiz questions from chat history."""
        # Format the chat history
        chat_history = format_chat_history(input.chat_messages)
        parties = format_parties(input.parties)

        # Build prompts
        system_prompt = SYSTEM_PROMPT
        user_prompt = GENERATION_PROMPT.format(
            topic=input.topic,
            num_questions=input.num_questions,
            parties=parties,
            chat_history=chat_history,
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        # Generate with structured output
        result = await self._llm.generate_structured(
            messages=messages,
            output_schema=QuizGeneratorOutput,
            temperature=0.3,  # Some creativity for diverse questions
        )

        logger.info(
            f"Generated {len(result.questions)} quiz questions for topic: {input.topic}"
        )
        return result

    def convert_to_quiz_questions(
        self,
        output: QuizGeneratorOutput,
        topic: str,
    ) -> list[QuizQuestion]:
        """Convert generated questions to QuizQuestion models.

        The LLM generates 4 content options; we append "Weiß ich nicht"
        as a fifth option here so participants can explicitly opt out of
        guessing when they didn't encounter the relevant content.
        ``correct_index`` stays 0-3 because the don't-know option is
        never the correct answer.
        """
        questions = []
        for gen_q in output.questions:
            options_with_dontknow = [*gen_q.options, "Weiß ich nicht"]
            # Drop any partial-credit index that accidentally points at the
            # correct answer or out of range — a malformed model output
            # shouldn't produce nonsensical 0.5 grading.
            partial_indices = sorted(
                {
                    i
                    for i in gen_q.partial_credit_indices
                    if 0 <= i <= 3 and i != gen_q.correct_index
                }
            )
            question = QuizQuestion(
                id=str(uuid4()),
                question=gen_q.question,
                options=options_with_dontknow,
                correct_index=gen_q.correct_index,
                party=gen_q.party,
                question_type=gen_q.question_type,
                is_overlap_question=gen_q.is_overlap_question,
                partial_credit_indices=partial_indices,
                topic=topic,
                source_excerpt=gen_q.source_excerpt,
            )
            questions.append(question)
        return questions

"""Implementation of quiz generator agent."""

import logging
import re
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage

from src.guided_exploration.agents.base import BaseAgent
from src.guided_exploration.agents.llm_provider import LLMProvider
from src.exploration_study.agents.quiz_generator.interface import (
    ChatMessage,
    GeneratedQuestion,
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


OVERLAP_META_OPTION = "Mehrere der genannten Parteien"


class QuizValidationError(ValueError):
    """Raised when generated questions fail post-generation validation.

    Carries the offending question (for logging/retry diagnostics) along
    with the human-readable reason.
    """

    def __init__(self, reason: str, question: GeneratedQuestion) -> None:
        super().__init__(reason)
        self.reason = reason
        self.question = question


def _normalize_for_match(text: str) -> str:
    """Collapse whitespace, lowercase, strip cosmetic markdown and outer punctuation.

    The LLM occasionally adds/drops trailing punctuation or wraps the
    excerpt in quotes when copying; normalizing both sides catches the
    legitimate cases without inviting fuzzy false-positives.

    We also strip cosmetic markdown markers (``*``, ``**``, ``_``, ``__``,
    backticks, list/heading/blockquote line prefixes) because the
    participant sees rendered markdown, not raw asterisks — so an excerpt
    that drops/keeps an emphasis marker mid-block is still a faithful
    quote of what they actually saw. Custom inline tokens like
    ``[PARTY_BADGE:venus]`` and ``[venus-klima-001]`` are preserved
    because we only strip the markdown syntax, not bracketed content.
    """
    s = text

    # Code fences and inline backticks — purely cosmetic.
    s = re.sub(r"```[a-zA-Z0-9_-]*", "", s)
    s = s.replace("`", "")

    # Bold/italic emphasis: drop the markers, keep the content. Order
    # matters — handle the doubled forms before the singles so we don't
    # leave a stray marker behind.
    s = re.sub(r"\*\*", "", s)
    s = re.sub(r"__", "", s)
    s = re.sub(r"\*", "", s)
    s = re.sub(r"(?<!\w)_|_(?!\w)", "", s)

    # Leading line markers (list bullets, ordered-list numbers, headings,
    # blockquotes). Apply per-line so we don't eat content mid-sentence.
    s = re.sub(r"(?m)^\s*(?:[-*+]\s+|\d+\.\s+|#{1,6}\s+|>\s+)", "", s)

    s = s.lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s.strip("\"'„“”«»‚‘’.,;:!?-—– ")


def _validate_generated_questions(
    questions: list[GeneratedQuestion],
    chat_messages: list[ChatMessage],
) -> None:
    """Validate generated questions; raise QuizValidationError on first failure.

    The retry loop in the service relies on the exception carrying the
    offending question so it can log a useful diagnostic before re-prompting.
    """
    normalized_chat = [
        _normalize_for_match(msg.content)
        for msg in chat_messages
        if msg.content
    ]

    for q in questions:
        # source_excerpts: must be present and verbatim from the chat
        if not q.source_excerpts:
            raise QuizValidationError(
                "source_excerpts is empty",
                q,
            )
        for excerpt in q.source_excerpts:
            if not excerpt or not excerpt.strip():
                raise QuizValidationError(
                    "source_excerpts contains an empty entry",
                    q,
                )
            normalized = _normalize_for_match(excerpt)
            if not normalized:
                raise QuizValidationError(
                    "source_excerpts contains an entry with no content after normalization",
                    q,
                )
            if not any(normalized in chat for chat in normalized_chat):
                raise QuizValidationError(
                    f"source_excerpt is not a verbatim substring of any chat message: {excerpt!r}",
                    q,
                )

        # Overlap questions: meta-option, ≥2 partial credits, ≥2 excerpts
        if q.is_overlap_question:
            if not (0 <= q.correct_index < len(q.options)):
                raise QuizValidationError(
                    f"correct_index {q.correct_index} out of range for options",
                    q,
                )
            if q.options[q.correct_index].strip() != OVERLAP_META_OPTION:
                raise QuizValidationError(
                    "overlap question correct_index does not point at "
                    f"'{OVERLAP_META_OPTION}'",
                    q,
                )
            if len(q.partial_credit_indices) < 2:
                raise QuizValidationError(
                    "overlap question must have at least 2 partial_credit_indices "
                    "(one per overlapping party)",
                    q,
                )
            if len(q.source_excerpts) < 2:
                raise QuizValidationError(
                    "overlap question must have at least 2 source_excerpts "
                    "(one per overlapping party)",
                    q,
                )
        else:
            if q.partial_credit_indices:
                raise QuizValidationError(
                    "non-overlap question must have empty partial_credit_indices",
                    q,
                )


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

        if input.previous_validation_error:
            user_prompt += (
                "\n\n---\n\n"
                "**Vorheriger Versuch wurde vom Validator verworfen.** "
                "Grund (technisch):\n"
                f"```\n{input.previous_validation_error}\n```\n"
                "Korrigiere genau diesen Fehler. Wenn der Grund auf einen "
                "nicht-wörtlichen `source_excerpt` hinweist: dieser Excerpt "
                "stand so NICHT im Chat. Suche stattdessen einen kürzeren, "
                "zusammenhängenden Substring, der wirklich existiert — oder "
                "lass die betroffene Frage komplett weg, statt sie zu retten."
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
        chat_messages: list[ChatMessage],
    ) -> list[QuizQuestion]:
        """Convert generated questions to QuizQuestion models.

        Validates the LLM output before conversion. On validation failure
        raises QuizValidationError so the caller can retry.

        The LLM generates 4 content options; we append "Weiß ich nicht"
        as a fifth option here so participants can explicitly opt out of
        guessing when they didn't encounter the relevant content.
        ``correct_index`` stays 0-3 because the don't-know option is
        never the correct answer.
        """
        _validate_generated_questions(output.questions, chat_messages)

        questions = []
        for gen_q in output.questions:
            options_with_dontknow = [*gen_q.options, "Weiß ich nicht"]
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
                question_type=gen_q.question_type,
                is_overlap_question=gen_q.is_overlap_question,
                partial_credit_indices=partial_indices,
                topic=topic,
                source_excerpts=gen_q.source_excerpts,
            )
            questions.append(question)
        return questions

"""Interface models for quiz generator agent."""

from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A message from the chat history."""

    role: str = Field(..., description="Role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class GeneratedQuestion(BaseModel):
    """A generated quiz question from the LLM."""

    question_type: Literal["A", "B", "C"] = Field(
        ...,
        description=(
            "Question type — MUST be decided FIRST and MUST match question/option "
            "shape per the system prompt. A = 'Welche Partei …?' (options are the "
            "three party badges + a meta-option). B = 'Wie steht [PARTY_BADGE:X] "
            "zu …?' (options are stances). C = 'Welche Aussage trifft auf "
            "[PARTY_BADGE:X] zu?' (options are short statements)."
        ),
    )
    question: str = Field(..., description="The question text")
    options: list[str] = Field(
        ...,
        description="List of 4 answer options",
        min_length=4,
        max_length=4,
    )
    correct_index: int = Field(
        ...,
        description="Index of the correct answer (0-3)",
        ge=0,
        le=3,
    )
    is_overlap_question: bool = Field(
        default=False,
        description=(
            "True if the question targets a known cross-party overlap (e.g. "
            "Klimageld is held by both Venus and Mars). For Type A overlap "
            "questions, the correct answer MUST be the meta-option "
            "'Mehrere der genannten Parteien' and partial_credit_indices "
            "MUST list the individual-party options that earn 0.5 credit "
            "(at least two)."
        ),
    )
    partial_credit_indices: list[int] = Field(
        default_factory=list,
        description=(
            "Indices of answer options (0-3) that earn 0.5 partial credit "
            "instead of 0. Used for Type A overlap questions where picking "
            "ONE of the two correct parties is partially right but misses "
            "the overlap. MUST NOT include the fully-correct index. MUST "
            "have at least two entries for overlap questions. Empty for "
            "non-overlap questions."
        ),
    )
    source_excerpts: list[str] = Field(
        ...,
        description=(
            "Verbatim excerpts from the chat that this question is based on. "
            "Each entry MUST be an exact, unmodified substring of an "
            "assistant message in the chat — copy the text exactly, do not "
            "paraphrase. For overlap questions, provide at least two "
            "excerpts (one citing each involved party's position)."
        ),
        min_length=1,
    )


class QuizGeneratorInput(BaseModel):
    """Input for quiz generation."""

    topic: str = Field(..., description="The topic that was explored")
    parties: list[str] = Field(..., description="List of party names in the study")
    chat_messages: list[ChatMessage] = Field(
        ...,
        description="The chat history from the exploration session",
    )
    num_questions: int = Field(
        default=10,
        description="Number of questions to generate (1-15)",
        ge=1,
        le=15,
    )
    previous_validation_error: str | None = Field(
        default=None,
        description=(
            "On retry, the validator's reason for rejecting the previous "
            "attempt. Surfaced to the LLM so it can correct the specific "
            "failure mode rather than blindly regenerating."
        ),
    )


class QuizGeneratorOutput(BaseModel):
    """Output from quiz generation."""

    questions: list[GeneratedQuestion] = Field(
        ...,
        description="The generated quiz questions",
    )
    generation_notes: str | None = Field(
        default=None,
        description="Any notes about the generation process",
    )

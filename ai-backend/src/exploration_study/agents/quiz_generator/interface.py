"""Interface models for quiz generator agent."""

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A message from the chat history."""

    role: str = Field(..., description="Role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class GeneratedQuestion(BaseModel):
    """A generated quiz question from the LLM."""

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
    party: str = Field(..., description="The party this question is about")
    source_excerpt: str = Field(
        ...,
        description="Brief excerpt from chat that this question is based on",
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

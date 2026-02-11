# SPDX-FileCopyrightText: 2025 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from enum import Enum

from pydantic import BaseModel, Field
from langchain_core.language_models.chat_models import BaseChatModel


class LLMSize(str, Enum):
    SMALL = "small"
    LARGE = "large"


class LLM(BaseModel):
    name: str = Field(..., description="The name of the language model.")
    model: BaseChatModel = Field(..., description="The language model.")
    sizes: list[LLMSize] = Field(
        ..., description="The sizes as which the LLM is considered."
    )
    priority: int = Field(
        ...,
        description="The priority for using this LLM above other options. The higher the number, the higher the priority.",
    )
    is_at_rate_limit: bool = Field(
        ...,
        description="Boolean True, if the model is at rate limit, otherwise False.",
    )
    premium_only: bool = Field(
        description="Boolean True, if the model is only available for premium users, otherwise False.",
        default=False,
    )
    back_up_only: bool = Field(
        description="Boolean True, if the model is only used as a backup if all other models are at a rate limit, otherwise False.",
        default=False,
    )

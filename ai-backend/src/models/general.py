# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from pydantic import BaseModel, Field
from langchain_core.language_models.chat_models import BaseChatModel


class LLM(BaseModel):
    name: str = Field(..., description="The name of the language model.")
    model: BaseChatModel = Field(..., description="The language model.")
    priority: int = Field(
        ...,
        description="The priority for using this LLM above other options. The higher the number, the higher the priority.",
    )
    back_up_only: bool = Field(
        description="Boolean True, if the model is only used as a backup if all other models fail, otherwise False.",
        default=False,
    )

# SPDX-FileCopyrightText: 2025 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import datetime
from pydantic import BaseModel, Field


class PartySource(BaseModel):
    name: str = Field(..., description="The Name of the Document")
    publish_date: datetime = Field(..., description="The Publish Date of the Document")
    storage_url: str = Field(..., description="The Storage URL of the Document")

# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Conversation-history formatting helpers for classifier / agent prompts."""

from src.guided_exploration.models import (
    Conversation,
    MessageRole,
    SessionMessage,
    SessionMessageType,
)


def format_session_history(
    messages: list[SessionMessage],
    limit: int = 10,
    per_message_chars: int = 2000,
) -> list[str]:
    """Format session messages as ``Nutzer: …`` / ``Assistent: …`` lines.

    Truncates each message to ``per_message_chars`` chars to keep prompts
    bounded. The classifier path uses the default 200 — short, since
    classification only needs surface-level context. The chip generator
    passes a much larger cap so it can actually see what was covered in
    earlier rich replies and avoid suggesting redundant follow-ups.
    Returns the most recent ``limit`` messages with non-empty text content.
    """
    recent = [
        m
        for m in messages
        if m.content
        and m.type in (SessionMessageType.USER, SessionMessageType.ASSISTANT)
    ][-limit:]

    history: list[str] = []
    for msg in recent:
        role = "Nutzer" if msg.type == SessionMessageType.USER else "Assistent"
        msg_content = msg.content or ""
        content = (
            msg_content[:per_message_chars] + "..."
            if len(msg_content) > per_message_chars
            else msg_content
        )
        history.append(f"{role}: {content}")
    return history


def format_leaf_history(
    conversation: Conversation | None,
    limit: int = 10,
) -> list[str]:
    """Format leaf-conversation messages as classifier-context lines.

    Truncates each message to 800 chars — enough to preserve most
    back-references while keeping the prompt bounded. Structured (non-string)
    content renders as ``[Strukturierter Inhalt]``.
    """
    if not conversation or not conversation.messages:
        return []

    history: list[str] = []
    for msg in conversation.messages[-limit:]:
        role = "Nutzer" if msg.role == MessageRole.USER else "Assistent"
        content = (
            msg.content
            if isinstance(msg.content, str)
            else "[Strukturierter Inhalt]"
        )
        content = content[:800] + "..." if len(content) > 800 else content
        history.append(f"{role}: {content}")
    return history


def extract_last_assistant_message(
    conversation: Conversation | None,
) -> str | None:
    """Return the most recent assistant text message in full.

    The classifier needs the untruncated last assistant turn to resolve
    short affirmations ("gerne", "ja") against the specific question the
    assistant just asked. The truncated entry in the history list would
    hide the question if the message is longer than 200 chars.
    """
    if not conversation or not conversation.messages:
        return None
    for msg in reversed(conversation.messages):
        if msg.role != MessageRole.ASSISTANT:
            continue
        if isinstance(msg.content, str):
            return msg.content
    return None

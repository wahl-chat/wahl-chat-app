# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""One generic-chat turn as the chat's existing SSE events.

Order: responding_parties ["wahl-chat"] → tool_status* → sources_ready →
text deltas + party_chunk → party_complete → related_items (unanchored
turns with a match) → quick_replies_title. Only a feed button's first
question is cached (see ``presets``); typed questions depend on the day's
feed and the web.
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Literal, Optional

from fastapi import Request as FastAPIRequest
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    UserPromptPart,
)
from pydantic_ai.run import AgentRunResultEvent

from src.core.sse import (
    DONE,
    data_event,
    finish,
    finish_step,
    start_message,
    text_delta,
    text_end,
    text_start,
)
from src.core.utils import (
    GENERIC_ERROR_MESSAGE,
    build_chat_history_string,
    sanitize_references,
)
from src.generic_chat import citation_check
from src.generic_chat.citations import drop_unknown_citations
from src.generic_chat import agent as agent_module
from src.generic_chat import presets, prompt, related
from src.generic_chat import tools
from src.generic_chat.schemas import GenericChatDeps, NumberedDocument, ProcessStep
from src.models.chat import Message, Role
from src.models.context import Context
from src.models.dtos import (
    PartyResponseCompleteDto,
    QuickRepliesAndTitleDto,
    SourcesDto,
    Status,
    StatusIndicator,
)
from src.models.party import WAHL_CHAT_PARTY
from src.services.chat.chatbot_async import generate_chat_title_and_chick_replies
from src.services.firebase_service import aget_parties_for_context

logger = logging.getLogger(__name__)

PARTY_ID = WAHL_CHAT_PARTY.party_id
_MAX_HISTORY_TURNS = 20
_ERROR_ANSWER = (
    "Es tut mir Leid, leider ist ein Fehler aufgetreten. Bitte versuche es später erneut."
)
# Earlier answers cite an earlier turn's sources; those numbers do not apply here.
_CITATION_RE = re.compile(r"\s?\[\d+(?:\s*,\s*\d+)*\]")

ToolState = Literal["running", "done"]

# (running, done) per language.
_TOOL_LABELS: dict[str, dict[str, tuple[str, str]]] = {
    "search": {
        "de": ("Durchsuche Quellen …", "Quellen durchsucht"),
        "en": ("Searching sources …", "Sources searched"),
    },
    "get_vote": {
        "de": ("Suche Abstimmung …", "Abstimmung nachgeschlagen"),
        "en": ("Looking up the vote …", "Vote looked up"),
    },
    "get_debate": {
        "de": ("Lade Debatte …", "Debatte geladen"),
        "en": ("Loading the debate …", "Debate loaded"),
    },
    "get_process": {
        "de": ("Lese das Verfahren …", "Verfahren gelesen"),
        "en": ("Reading the procedure …", "Procedure read"),
    },
    "list_feed_items": {
        "de": ("Prüfe den Feed …", "Feed geprüft"),
        "en": ("Checking the feed …", "Feed checked"),
    },
    "web_search": {
        "de": ("Suche im Web …", "Web durchsucht"),
        "en": ("Searching the web …", "Web searched"),
    },
}


def resolve_model() -> Any:
    return agent_module.build_model()


def tool_label(tool: str, state: ToolState, language: str) -> str:
    running, done = _TOOL_LABELS.get(tool, {}).get(
        language, _TOOL_LABELS.get(tool, {}).get("de", (tool, tool))
    )
    return running if state == "running" else done


def _tool_status(
    session_id: str, call_id: str, tool: str, state: ToolState, language: str
) -> str:
    return data_event(
        {
            "type": "tool_status",
            "session_id": session_id,
            "call_id": call_id,
            "tool": tool,
            "label": tool_label(tool, state, language),
            "state": state,
        }
    )


def _sources_ready(session_id: str, deps: GenericChatDeps) -> str:
    dto = SourcesDto(
        session_id=session_id,
        party_id=PARTY_ID,
        rag_query=None,
        sources=deps.sources.snapshot(),
    )
    return data_event({"type": "sources_ready", **dto.model_dump()})


def _party_chunk(session_id: str, chunk: str) -> str:
    return data_event(
        {
            "type": "party_chunk",
            "session_id": session_id,
            "party_id": PARTY_ID,
            "chunk_content": chunk,
        }
    )


def _error_complete(session_id: str) -> str:
    return data_event(
        {
            "type": "party_complete",
            "session_id": session_id,
            "party_id": PARTY_ID,
            "complete_message": _ERROR_ANSWER,
            "message_id": None,
            "status": {"indicator": "error", "message": GENERIC_ERROR_MESSAGE},
        }
    )


def message_history(body: Any) -> list[ModelMessage]:
    """Prior turns as model messages; the current question is the run's prompt."""
    turns = list(body.chat_history)
    if turns and turns[-1].role == Role.USER and turns[-1].content == body.user_message:
        turns = turns[:-1]
    history: list[ModelMessage] = []
    for turn in turns[-_MAX_HISTORY_TURNS:]:
        if turn.role == Role.USER:
            history.append(ModelRequest(parts=[UserPromptPart(turn.content)]))
        else:
            text = _CITATION_RE.sub("", turn.content)
            history.append(ModelResponse(parts=[TextPart(text)]))
    return history


def _text_of(event: object) -> Optional[str]:
    if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
        return event.part.content
    if isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
        return event.delta.content_delta
    return None


async def _quick_replies(
    body: Any, answer: str, replies: Optional[list[str]] = None, guidelines: Optional[str] = None
) -> Optional[QuickRepliesAndTitleDto]:
    turns = [
        Message(role=t.role, content=t.content, party_id=t.party_id)
        for t in body.chat_history
    ]
    if not turns or turns[-1].content != body.user_message:
        turns.append(Message(role=Role.USER, content=body.user_message))
    turns.append(Message(role=Role.ASSISTANT, content=answer, party_id=PARTY_ID))
    try:
        generated = await generate_chat_title_and_chick_replies(
            chat_history_str=build_chat_history_string(turns, []),
            chat_title="Noch kein Titel vergeben",
            parties_in_chat=[],
            wahl_chat_assistant_last_responded=True,
            quick_reply_guidelines=guidelines or prompt.quick_reply_guidelines([]),
        )
    except Exception as exc:  # noqa: BLE001 (quick replies are optional)
        logger.error("generic chat: quick replies failed: %s", exc, exc_info=True)
        return None
    return QuickRepliesAndTitleDto(
        session_id=body.session_id,
        quick_replies=replies or generated.quick_replies,
        title=generated.chat_title,
    )


_CHECK_TIMEOUT_S = 5.0
_ANCHOR_TIMEOUT_S = 20.0
_QUICK_REPLIES_TIMEOUT_S = 10.0
_CACHE_WRITE_TIMEOUT_S = 5.0
# Past the answer's end; the search began with the turn.
_RELATED_TIMEOUT_S = 3.0


def _entry(deps: GenericChatDeps, number: int) -> dict:
    return deps.sources.entries[number] if number < len(deps.sources.entries) else {}


def _voice(deps: GenericChatDeps, number: int) -> Optional[str]:
    """A party's own words, press, or the record."""
    entry = _entry(deps, number)
    party = entry.get("party_id")
    if party:
        # The CSU speaks within the Union's Fraktion.
        return "cdu" if party == "csu" else str(party)
    return "press" if entry.get("source_type") == "web" else "record"


def _speaker(deps: GenericChatDeps, number: int) -> Optional[str]:
    entry = _entry(deps, number)
    if entry.get("source_type") != "parliamentary_speech":
        return None
    name = str(entry.get("source") or "").split(",")[0].strip()
    return name or None


def _step_documents(result: Any) -> list[NumberedDocument]:
    """A procedure's citable steps, as text the citation check can read."""
    steps: list[ProcessStep] = list(getattr(result, "steps", None) or [])
    return [
        NumberedDocument(
            id=step.id,
            source_type="procedure_step",
            title=f"{step.name} ({step.chamber})",
            date=step.date,
            text=" ".join(
                filter(
                    None,
                    [step.date, step.chamber, step.name, step.document, *step.decisions, step.summary],
                )
            ),
        )
        for step in steps
        if step.id is not None
    ]


def _documents_of(result: Any) -> list[NumberedDocument]:
    return [*(getattr(result, "documents", None) or []), *_step_documents(result)]


async def _checked(
    answer: str, deps: GenericChatDeps, documents: list[NumberedDocument]
) -> str:
    """The answer with each citation re-pointed to a source of the same voice
    that states its sentence, or dropped; unchanged when the check fails."""
    if not answer or not documents or not citation_check.enabled():
        return answer
    sources = [
        citation_check.Source(
            # The date is in metadata only for votes, steps and web results.
            id=d.id, title=" · ".join(filter(None, [d.date, d.title])), text=d.text,
            voice=_voice(deps, d.id), speaker=_speaker(deps, d.id),
        )
        for d in documents
    ]
    # Registered, but no text was shown to check against: kept as cited.
    keep = frozenset(range(len(deps.sources.entries))) - {s.id for s in sources}
    stats = citation_check.RepairStats()
    try:
        result = await asyncio.wait_for(citation_check.check(answer, sources), _CHECK_TIMEOUT_S)
        repaired = citation_check.repair(answer, result.verdicts, sources, keep=keep, stats=stats)
    except Exception as exc:  # noqa: BLE001 (the unchecked answer still stands)
        deps.degraded = True
        logger.warning("citation check failed, answer kept: %r", exc)
        return answer
    logger.info(
        "citation check: %d citations, %d kept, %d re-pointed, %d dropped, %.1fs, %d/%d tokens",
        stats.kept + stats.repointed + stats.dropped,
        stats.kept,
        stats.repointed,
        stats.dropped,
        result.seconds,
        result.input_tokens,
        result.output_tokens,
    )
    return repaired


def _cancel(*tasks: Optional[asyncio.Task[Any]]) -> None:
    for task in tasks:
        if task is not None:
            task.cancel()


async def _related_items(task: Optional[asyncio.Task[list[str]]]) -> list[str]:
    if task is None:
        return []
    try:
        return await asyncio.wait_for(task, _RELATED_TIMEOUT_S)
    except Exception as exc:  # noqa: BLE001 (no carousel, the answer stands)
        logger.warning("related feed items skipped: %r", exc)
        return []


def _replay(session_id: str, turn: presets.CachedTurn) -> list[str]:
    """A cached answer as the same events a live turn sends."""
    text_id = str(uuid.uuid4())
    sources = SourcesDto(
        session_id=session_id, party_id=PARTY_ID, rag_query=None, sources=turn.sources
    )
    complete = PartyResponseCompleteDto(
        session_id=session_id,
        party_id=PARTY_ID,
        complete_message=turn.answer,
        message_id=text_id,
        status=Status(indicator=StatusIndicator.SUCCESS, message="Success"),
    )
    events = [
        data_event({"type": "sources_ready", **sources.model_dump()}),
        text_start(text_id),
        text_delta(text_id, turn.answer),
        _party_chunk(session_id, turn.answer),
        text_end(text_id),
        data_event({"type": "party_complete", **complete.model_dump()}),
    ]
    if turn.quick_replies:
        replies = QuickRepliesAndTitleDto(
            session_id=session_id, quick_replies=turn.quick_replies, title=turn.title
        )
        events.append(data_event({"type": "quick_replies_title", **replies.model_dump()}))
    return [*events, finish_step(), finish(), DONE]


async def stream_generic_chat(
    body: Any,
    request: Optional[FastAPIRequest],
    context: Context,
) -> AsyncGenerator[str, None]:
    """SSE payloads for one turn in a general context (see module docstring)."""
    session_id: str = body.session_id
    language: str = getattr(body, "language", "de") or "de"
    for part in start_message(str(uuid.uuid4())):
        yield part
    yield data_event(
        {"type": "responding_parties", "session_id": session_id, "party_ids": [PARTY_ID]}
    )

    text_id: Optional[str] = None
    answer = ""
    guidelines: Optional[str] = None
    cache_key: Optional[str] = None
    replies_task: Optional[asyncio.Task[Optional[QuickRepliesAndTitleDto]]] = None
    related_task: Optional[asyncio.Task[list[str]]] = None
    try:
        deps = GenericChatDeps(
            context=context,
            parties=await aget_parties_for_context(context.context_id),
            language="en" if language == "en" else "de",
            session_id=session_id,
        )
        deps.set_focus(list(getattr(body, "party_ids", None) or []))
        guidelines = prompt.quick_reply_guidelines(deps.parties)

        anchor = getattr(body, "anchor", None)
        history = message_history(body)
        parliament = tools.parliament_for(deps)
        if anchor is None and parliament is not None and related.wanted(
            parliament, body.user_message, bool(history)
        ):
            related_task = asyncio.create_task(
                related.safe_find(body.user_message, parliament)
            )
        # A button's question opens the chat; later turns are the reader's own.
        if anchor is not None and not history:
            deps.preset = getattr(body, "preset", None)
        if anchor is not None:
            anchor_tool = (
                "get_process"
                if anchor.vorgang_id
                else "get_debate" if anchor.feed_item_id else "get_vote"
            )
            yield _tool_status(session_id, "anchor", anchor_tool, "running", language)
            try:
                deps.anchor = await asyncio.wait_for(
                    tools.resolve_anchor(
                        deps, anchor, deps.fraktionen() if deps.preset == "why" else None
                    ),
                    _ANCHOR_TIMEOUT_S,
                )
            except Exception as exc:  # noqa: BLE001 (the turn goes on without its Bezug)
                deps.degraded = True
                logger.warning(
                    "generic chat: anchor %s failed: %r", anchor.model_dump(exclude_none=True), exc
                )
            yield _tool_status(session_id, "anchor", anchor_tool, "done", language)

        if deps.preset is not None and deps.anchor is not None:
            cache_key = presets.cache_key(deps, body.user_message, resolve_model())
            cached = await presets.aload(cache_key)
            if cached is not None:
                logger.info("generic chat: preset answer from cache")
                for part in _replay(session_id, cached):
                    yield part
                return

        # Every document the model saw this turn, for the citation check.
        anchored = _documents_of(deps.anchor.result) if deps.anchor else []
        seen: dict[int, NumberedDocument] = {d.id: d for d in anchored}
        sources_sent = 0
        output: Optional[str] = None
        async with agent_module.agent.run_stream_events(
            body.user_message,
            message_history=history,
            deps=deps,
            model=resolve_model(),
            usage_limits=agent_module.USAGE_LIMITS,
            timeout=agent_module.TURN_TIMEOUT_S,
        ) as events:
            async for event in events:
                if isinstance(event, FunctionToolCallEvent):
                    yield _tool_status(
                        session_id, event.tool_call_id, event.part.tool_name, "running", language
                    )
                elif isinstance(event, FunctionToolResultEvent):
                    returned = _documents_of(getattr(event.part, "content", None))
                    seen.update({d.id: d for d in returned})
                    yield _tool_status(
                        session_id, event.tool_call_id, event.part.tool_name, "done", language
                    )
                elif isinstance(event, AgentRunResultEvent):
                    output = str(event.result.output or "")
                    logger.info(
                        "generic chat run: %d model requests, %d sources",
                        event.result.usage.requests,
                        len(deps.sources.entries),
                    )
                elif (delta := _text_of(event)):
                    if text_id is None:
                        yield _sources_ready(session_id, deps)
                        sources_sent = len(deps.sources.entries)
                        text_id = str(uuid.uuid4())
                        yield text_start(text_id)
                    answer += delta
                    yield text_delta(text_id, delta)
                    yield _party_chunk(session_id, delta)

        if text_id is None:
            # Nothing streamed (e.g. an empty answer): send what the run returned.
            yield _sources_ready(session_id, deps)
            sources_sent = len(deps.sources.entries)
            text_id = str(uuid.uuid4())
            yield text_start(text_id)
            answer = output or ""
            if answer:
                yield text_delta(text_id, answer)
                yield _party_chunk(session_id, answer)
        yield text_end(text_id)
        message_id, text_id = text_id, None
        if len(deps.sources.entries) != sources_sent:
            # A tool ran after the text began; the client replaces the sources.
            yield _sources_ready(session_id, deps)

        # The final response alone: text a model wrote before a tool call is
        # not part of the answer.
        answer = output or answer
        answer = drop_unknown_citations(sanitize_references(answer), len(deps.sources.entries))
        # A name left several procedures open: the choices replace the
        # generated replies; tapping one sends its exact title.
        choices = [choice.label for choice in deps.choices]
        replies_task = asyncio.create_task(
            asyncio.wait_for(
                _quick_replies(body, answer, replies=choices or None, guidelines=guidelines),
                _QUICK_REPLIES_TIMEOUT_S,
            )
        )
        answer = await _checked(answer, deps, list(seen.values()))
        complete = PartyResponseCompleteDto(
            session_id=session_id,
            party_id=PARTY_ID,
            complete_message=answer,
            message_id=message_id,
            status=Status(indicator=StatusIndicator.SUCCESS, message="Success"),
        )
        yield data_event({"type": "party_complete", **complete.model_dump()})
    except (asyncio.CancelledError, GeneratorExit):
        # The client left mid-turn: no reply call keeps running for nobody.
        _cancel(replies_task, related_task)
        raise
    except Exception as exc:  # noqa: BLE001 (terminal error contract, as the election path)
        logger.error("generic chat turn failed: %s", exc, exc_info=True)
        _cancel(replies_task, related_task)
        if text_id is not None:
            yield text_end(text_id)
        yield data_event({"type": "error", "message": GENERIC_ERROR_MESSAGE})
        yield _error_complete(session_id)
        yield finish_step()
        yield finish()
        yield DONE
        return

    if request is not None and await request.is_disconnected():
        logger.info("generic chat: client disconnected, skipping quick replies")
        _cancel(replies_task, related_task)
        return
    items = await _related_items(related_task)
    if items:
        yield data_event(
            {"type": "related_items", "session_id": session_id,
             "items": [{"id": item_id} for item_id in items]}
        )
    try:
        quick_replies = await replies_task if replies_task is not None else None
    except Exception as exc:  # noqa: BLE001 (quick replies are optional)
        logger.warning("generic chat: quick replies failed: %r", exc)
        quick_replies = None
    if quick_replies is not None:
        yield data_event({"type": "quick_replies_title", **quick_replies.model_dump()})
    yield finish_step()
    yield finish()
    yield DONE
    # An answer that stands on a failed lookup is not served to everyone.
    # Awaited inside the request: an instance gets CPU only while one is open.
    if cache_key is not None and answer and not deps.degraded:
        stored_at = datetime.now(timezone.utc)
        turn = presets.CachedTurn(
            answer=answer,
            sources=deps.sources.snapshot(),
            quick_replies=quick_replies.quick_replies if quick_replies else [],
            title=quick_replies.title if quick_replies else "",
            created_at=stored_at,
            expire_at=stored_at + presets.MAX_AGE,
        )
        try:
            await asyncio.wait_for(presets.astore(cache_key, turn), _CACHE_WRITE_TIMEOUT_S)
        except TimeoutError:
            logger.warning("preset cache write timed out")

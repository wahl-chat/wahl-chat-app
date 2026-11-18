# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""The generic chat agent (Pydantic AI): Gemini on Vertex, then Gemini on AI
Studio, then OpenAI, with the tools from ``tools.py``."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, replace
from functools import lru_cache
from typing import Any, Awaitable, Callable, Optional, TypeVar

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext, Tool
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.messages import ModelRequest, ToolReturnPart, UserPromptPart
from pydantic_ai.models import Model, ModelRequestContext
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.usage import UsageLimits

from src.generic_chat import process, tools, web_context
from src.generic_chat.prompt import build_system_prompt
from src.generic_chat.schemas import (
    DebateResult,
    FeedItemsResult,
    GenericChatDeps,
    GetDebateInput,
    GetProcessInput,
    GetVoteInput,
    ListFeedItemsInput,
    ProcessResult,
    SearchInput,
    ToolResult,
    WebSearchInput,
)
from wahlchat_common.answer_rules import language_rule
from wahlchat_common.vertex_credentials import (
    get_vertex_credentials,
    vertex_enabled,
    vertex_location,
    vertex_project,
)

logger = logging.getLogger(__name__)

# ≈ three tool rounds plus the answer.
MAX_MODEL_REQUESTS = 4
TURN_TIMEOUT_S = 60.0
# After this, the next request gets no tools, so the answer starts in time.
_TOOLS_CUTOFF_S = 40.0
_TOOL_TIMEOUT_S = 20.0

# Same models as the top of RESPONSE_GENERATION_LLMS in src/config/llms.py.
GEMINI_MODEL = "gemini-3.6-flash"
OPENAI_MODEL = "gpt-5.6-terra"
_MODEL_SETTINGS = ModelSettings(thinking="minimal")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def build_model() -> Model:
    """Vertex → AI Studio → OpenAI, skipping tiers without credentials."""
    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.google import GoogleProvider
    from pydantic_ai.providers.google_cloud import GoogleCloudProvider
    from pydantic_ai.providers.openai import OpenAIProvider

    tiers: list[Model] = []
    if vertex_enabled():
        tiers.append(
            GoogleModel(
                GEMINI_MODEL,
                provider=GoogleCloudProvider(
                    credentials=get_vertex_credentials(),
                    project=vertex_project(),
                    location=vertex_location(),
                ),
                settings=_MODEL_SETTINGS,
            )
        )
    if google_key := os.getenv("GOOGLE_API_KEY"):
        tiers.append(
            GoogleModel(
                GEMINI_MODEL,
                provider=GoogleProvider(api_key=google_key),
                settings=_MODEL_SETTINGS,
            )
        )
    if openai_key := os.getenv("OPENAI_API_KEY"):
        tiers.append(
            OpenAIChatModel(
                OPENAI_MODEL,
                provider=OpenAIProvider(api_key=openai_key),
                settings=_MODEL_SETTINGS,
            )
        )
    if not tiers:
        raise RuntimeError("generic chat: no LLM credentials configured")
    logger.info("generic chat models: %s", [m.model_name for m in tiers])
    return tiers[0] if len(tiers) == 1 else FallbackModel(*tiers)


# ---------------------------------------------------------------------------
# Budget + language reminder
# ---------------------------------------------------------------------------


async def _within_budget(
    ctx: RunContext[GenericChatDeps], tool_def: ToolDefinition
) -> Optional[ToolDefinition]:
    """Hide every tool on the last allowed request (or late in the turn), so the
    model has to answer from what it already has."""
    out_of_requests = ctx.usage.requests >= MAX_MODEL_REQUESTS - 1
    out_of_time = time.monotonic() - ctx.deps.started_at > _TOOLS_CUTOFF_S
    # Open choices: the next answer is the question which one.
    asking = bool(ctx.deps.choices)
    # A feed button's answer is cached, so it stands on our data alone.
    off_web = tool_def.name == "web_search" and ctx.deps.preset is not None
    return None if out_of_requests or out_of_time or asking or off_web else tool_def



@dataclass
class RepeatLanguageRule(AbstractCapability[GenericChatDeps]):
    """Appends the language rule after tool results, for this request only,
    so long German sources do not pull the answer into German."""

    async def before_model_request(
        self,
        ctx: RunContext[GenericChatDeps],
        request_context: ModelRequestContext,
    ) -> ModelRequestContext:
        messages = request_context.messages
        last = messages[-1] if messages else None
        if isinstance(last, ModelRequest) and any(
            isinstance(part, ToolReturnPart) for part in last.parts
        ):
            reminder = UserPromptPart(language_rule(ctx.deps.language))
            request_context.messages = [
                *messages[:-1],
                replace(last, parts=[*last.parts, reminder]),
            ]
        return request_context


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

_R = TypeVar("_R", bound=BaseModel)


def _unknown(key: str, value: object, where: str) -> str:
    return (
        f"{key} {value} was not returned by any tool in this chat. Use the"
        f" {key} from {where}; never write one yourself."
    )


_FAILED = "This lookup failed. Answer without it and say briefly what is missing."


async def _logged(
    name: str,
    call: Callable[[], Awaitable[_R]],
    deps: GenericChatDeps,
    empty: type[_R],
    learn: bool = True,
) -> _R:
    """Run a tool; a failing lookup becomes a note, never the end of the turn."""
    started = time.monotonic()
    try:
        result = await call()
    except Exception as exc:  # noqa: BLE001 (the model answers from what it has)
        deps.degraded = True
        logger.warning("generic chat tool %s failed: %r", name, exc)
        return empty(note=_FAILED)  # type: ignore[call-arg]
    if learn:
        deps.learn(result)
    hits = len(getattr(result, "documents", None) or getattr(result, "items", None) or [])
    logger.info(
        "generic chat tool %s: %.2fs, %d hits", name, time.monotonic() - started, hits
    )
    return result


async def search(ctx: RunContext[GenericChatDeps], args: SearchInput) -> ToolResult:
    """Search our corpus of Bundestag votes, plenary speeches and party
    manifestos (query in German). Example: query 'Bürgergeld Sanktionen',
    source_types ['vote_record', 'parliamentary_speech']."""
    return await _logged("search", lambda: tools.search(ctx.deps, args), ctx.deps, ToolResult)


async def get_vote(ctx: RunContext[GenericChatDeps], args: GetVoteInput) -> DebateResult:
    """One roll-call vote by its poll_id (default: the chat's vote) with every
    party's tally, plus the debate on the same Drucksache when the feed has one.
    With party_ids, each party's statements and motions on the law, for 'why'
    questions."""
    poll_id = args.poll_id or ctx.deps.anchor_poll_id()
    if poll_id is None:
        return DebateResult(note="This chat is not about one vote: pass the poll_id from a vote document.")
    if not ctx.deps.knows("poll_id", poll_id):
        return DebateResult(note=_unknown("poll_id", poll_id, "a vote document"))
    return await _logged(
        "get_vote", lambda: tools.get_vote(ctx.deps, poll_id, args.party_ids), ctx.deps, DebateResult
    )


async def get_debate(
    ctx: RunContext[GenericChatDeps], args: GetDebateInput
) -> DebateResult:
    """The speeches of one debate (or the vote) a feed item covers."""
    if not ctx.deps.knows("feed_item_id", args.feed_item_id):
        return DebateResult(note=_unknown("feed_item_id", args.feed_item_id, "list_feed_items"))
    return await _logged(
        "get_debate", lambda: tools.get_debate(ctx.deps, args.feed_item_id), ctx.deps, DebateResult
    )


async def get_process(
    ctx: RunContext[GenericChatDeps], args: GetProcessInput
) -> ProcessResult:
    """One Bundestag procedure (law or motion) by vorgang_id or name: dated
    steps, decisions, and its votes, speeches and Drucksache passages. With
    party_ids, each party's statements and motions on it. An ambiguous name
    returns choices instead; then ask the user."""
    if args.vorgang_id is not None and not ctx.deps.knows("vorgang_id", args.vorgang_id):
        return ProcessResult(note=_unknown("vorgang_id", args.vorgang_id, "a search result's procedures, or pass the name"))
    # A bare number as name is an id too.
    if args.name and args.name.strip().isdigit() and not ctx.deps.knows("vorgang_id", args.name.strip()):
        return ProcessResult(note=_unknown("vorgang_id", args.name.strip(), "a search result's procedures, or pass the name"))
    result = await _logged(
        "get_process", lambda: process.get_process(ctx.deps, args), ctx.deps, ProcessResult
    )
    if result.procedure is not None:
        ctx.deps.choices = []
        await web_context.add_press(ctx.deps, result)
    elif result.choices:
        ctx.deps.choices = result.choices
    return result


async def list_feed_items(
    ctx: RunContext[GenericChatDeps], args: ListFeedItemsInput
) -> FeedItemsResult:
    """Published feed items (debates and votes) in a date window, for recaps.
    Not citable: fetch the items with get_debate / get_vote and cite those."""
    return await _logged(
        "list_feed_items", lambda: tools.list_feed_items(ctx.deps, args), ctx.deps, FeedItemsResult
    )


async def web_search(
    ctx: RunContext[GenericChatDeps], args: WebSearchInput
) -> ToolResult:
    """Search the web: scope 'news' for current events, 'civic' for how German
    politics and its institutions work (official sites only)."""
    return await _logged(
        "web_search", lambda: tools.web_search(ctx.deps, args), ctx.deps, ToolResult, learn=False
    )


TOOL_FUNCTIONS: tuple[Callable[..., Awaitable[Any]], ...] = (
    search,
    get_vote,
    get_debate,
    get_process,
    list_feed_items,
    web_search,
)

agent: Agent[GenericChatDeps, str] = Agent(
    deps_type=GenericChatDeps,
    output_type=str,
    tools=[
        Tool(fn, takes_ctx=True, prepare=_within_budget, timeout=_TOOL_TIMEOUT_S)
        for fn in TOOL_FUNCTIONS
    ],
    capabilities=[RepeatLanguageRule()],
    name="generic_chat",
)


@agent.instructions
def _instructions(ctx: RunContext[GenericChatDeps]) -> str:
    return build_system_prompt(ctx.deps)


USAGE_LIMITS = UsageLimits(request_limit=MAX_MODEL_REQUESTS)

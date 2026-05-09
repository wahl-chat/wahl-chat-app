#!/usr/bin/env python3
"""
End-to-end simulator for the exploration study.

Drives the participant lifecycle for pre-created sessions, using OpenAI as
the simulated participant. Each session's assigned condition (guided vs
baseline) is honored: guided sessions walk every leaf with two follow-ups
each then ask one final main-chat question; baseline sessions chat in a
straight loop. Quiz status is captured for validation.

The script talks to the running backend over HTTP/SSE for the chat
itself, and reads/writes session state directly via the Firebase repos
(same as the admin script) so it can dispatch the right handler per
session without extra coordination.

Usage:
    # Bring up the backend, then in another shell:
    poetry run python scripts/simulate_study_sessions.py \
        --study-id <id> \
        --base-url http://localhost:8080 \
        --concurrency 3 \
        --output-dir simulate_results

Requires OPENAI_API_KEY in the environment.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import random
import re
import sys
import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator

import aiohttp

# Add project root to path so we can import from src/
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Initialize Firebase before importing modules that use it
from src.firebase_service import db  # noqa: E402, F401

from src.exploration_study.models.quiz import QuizStatus  # noqa: E402
from src.exploration_study.models.session import SystemType  # noqa: E402
from src.exploration_study.models.state import StudyState  # noqa: E402
from src.exploration_study.services.session_repository import (  # noqa: E402
    get_session_repository,
)
from src.exploration_study.services.study_repository import (  # noqa: E402
    get_study_repository,
)

logger = logging.getLogger("simulate")


# =============================================================================
# Persona — knowledge-seeker only. No content stances, no preferences.
# =============================================================================

# Persona = study participant exploring the chatbot, not a real voter using
# the tool to inform their own life. The goal is to learn the positions of
# Venus / Mars / Saturn within the assigned topic — no personal stakes, no
# party preferences. The texture should be casual chat, not an interview:
# short, sometimes lazy phrasing, lowercase starts, the occasional fragment
# or "?" — but the *content* stays focused on understanding party positions.
PERSONA_SYSTEM = (
    "Du nimmst an einer Studie teil und chattest mit einem Bot über die "
    "Positionen der drei (fiktiven) Parteien Venus, Mars und Saturn. Du "
    "kennst die Parteien nicht und hast keine Vorlieben.\n\n"
    "## Dein Ziel — alle drei Parteien lernen\n"
    "Nach dem Chat kommt ein Quiz mit konkreten Fragen, welche Partei "
    "was fordert (Maßnahmen, Zahlen, Unterschiede). Du willst möglichst "
    "viele richtig beantworten. Dafür brauchst du zu **jeder** der drei "
    "Parteien (Venus, Mars, Saturn) konkrete inhaltliche Aussagen — "
    "nicht nur zu einer oder zweien.\n\n"
    "## Wie du fragst — Drei-Parteien-Reflex\n"
    "- Standardfrage ist eine **Vergleichsfrage über alle drei**: 'was "
    "sagen Venus, Mars und Saturn zu X?', 'wie unterscheiden sie sich "
    "bei X?', 'X — alle drei kurz?'. Nenne ruhig alle drei beim Namen.\n"
    "- Wenn die Bot-Antwort eine Partei auslässt, **direkt nachhaken**: "
    "'und Saturn dazu?', 'was ist mit Mars hier?', 'fehlt noch Venus'.\n"
    "- Wenn die Antwort eine Partei nur grob behandelt: 'mars konkreter?', "
    "'was genau fordert venus dazu?'.\n"
    "- Wenn ein Aspekt einer Partei interessant ist und du detailliert "
    "nachfragst, denk kurz danach 'wie machen das die anderen beiden?' "
    "und stell die nächste Frage entsprechend. Lass keine Partei links "
    "liegen.\n"
    "- Vermeide einseitige Drilldowns über mehrere Turns am Stück "
    "ausschließlich zu **einer** Partei. Maximal 1–2 Detail-Turns zu "
    "einer Partei, dann zurück zu den anderen.\n\n"
    "## Wie du tippst — wie ein echter Chatnutzer\n"
    "- Kurze Fragen, meist 1 Satz, oft nur Halbsatz oder Stichwort + "
    "Fragezeichen ('und Saturn dazu?', 'CBAM kurz?', 'wie genau?').\n"
    "- Klein-/Großschreibung locker, Punkt am Ende optional. Keine "
    "Interview-Floskeln wie 'Welche konkreten Maßnahmen schlagen die "
    "Parteien Venus, Mars und Saturn vor, …'.\n"
    "- Nachhaken ist gut: 'warum?', 'was heißt das?', 'okay und die "
    "anderen beiden?', 'unterschied venus vs mars hier?'.\n"
    "- KEINE Meinungen, keine persönliche Lebenslage, keine "
    "Parteibevorzugung. Du bringst dich nicht ein — dir geht's nur "
    "darum, die Positionen aller drei für das Quiz zu kennen.\n\n"
    "Antworte ausschließlich mit deinem nächsten Chat-Beitrag."
)


def _topic_label(topic: str) -> str:
    """Human-readable German label for the topic slug."""
    return {
        "klimaschutz": "Klimaschutz",
        "soziale-gerechtigkeit": "soziale Gerechtigkeit",
    }.get(topic, topic)


# =============================================================================
# Config / DTOs
# =============================================================================


@dataclass
class SimConfig:
    base_url: str
    output_dir: Path
    concurrency: int
    quiz_poll_timeout_seconds: int = 600
    quiz_poll_interval_seconds: int = 5
    # Baseline runs until the LLM-estimated elapsed time hits this budget,
    # mirroring the real 10-minute task cap. ``baseline_max_turns`` is a
    # safety hard-cap so the loop can't run forever if the estimate stays
    # implausibly low.
    baseline_budget_minutes: float = 10.0
    baseline_max_turns: int = 25
    followups_per_leaf_min: int = 1
    followups_per_leaf_max: int = 3
    # Probability of picking from the chatbot's `suggested_questions`
    # when it offers them (vs. generating a fresh persona-driven turn).
    # Set high because the suggestions are now the primary lever for
    # surfacing breadth — original turns sprinkle in occasionally.
    suggestion_pickup_prob: float = 0.85
    openai_model: str = "gpt-4o-mini"
    sse_idle_timeout_seconds: int = 120


@dataclass
class SessionReport:
    session_id: str
    group: str
    system: str
    topic: str
    chat_id: str | None = None
    started_at: str = ""
    finished_at: str = ""
    quiz_status: str | None = None
    quiz_error: str | None = None
    quiz_questions: list[dict] = field(default_factory=list)
    user_messages: list[str] = field(default_factory=list)
    assistant_messages: list[str] = field(default_factory=list)
    leaves_visited: list[str] = field(default_factory=list)
    error: str | None = None


# =============================================================================
# OpenAI helper for generating participant messages
# =============================================================================


class PersonaChat:
    """Minimal OpenAI wrapper that maintains a per-session message history."""

    def __init__(self, model: str, topic: str) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI()
        self._model = model
        topic_label = _topic_label(topic)
        self._history: list[dict[str, str]] = [
            {"role": "system", "content": PERSONA_SYSTEM},
            {
                "role": "system",
                "content": (
                    f"Themenfeld dieser Sitzung: {topic_label}. Bleib bei "
                    "diesem Thema. Versuche aktiv, zu **jeder** der drei "
                    "Parteien (Venus, Mars, Saturn) konkrete Positionen "
                    "zu erfahren — nicht nur zu einer oder zweien. Wenn "
                    "eine Antwort eine Partei auslässt oder nur streift, "
                    "frag nach. Schreib locker und kurz, nicht förmlich."
                ),
            },
        ]
        # Suggestions the persona has already used — avoid repeats when the
        # backend keeps surfacing the same idea across turns.
        self._used_suggestions: set[str] = set()

    def add_assistant(self, text: str) -> None:
        """Record what the chatbot replied (becomes 'user' from the persona's POV)."""
        # From the persona's perspective, the chatbot's reply is the
        # incoming "user" turn. Cap length so we don't bloat context.
        snippet = text[:1500]
        self._history.append({"role": "user", "content": snippet})

    def _record_user_turn(self, text: str) -> None:
        self._history.append({"role": "assistant", "content": text})

    def pick_suggestion(self, suggestions: list[str]) -> str | None:
        """Return an unused suggested question, or None if all are used/empty."""
        for s in suggestions:
            cleaned = (s or "").strip()
            if cleaned and cleaned not in self._used_suggestions:
                self._used_suggestions.add(cleaned)
                self._record_user_turn(cleaned)
                return cleaned
        return None

    async def next_user_turn(
        self,
        suggestions: list[str] | None = None,
        hint: str | None = None,
        pickup_prob: float = 0.65,
    ) -> str:
        """Generate the persona's next chat turn.

        With probability ``pickup_prob`` and an unused suggestion available,
        return one of the chatbot's proposed follow-ups verbatim — that's
        what real users do most of the time when buttons are offered.
        Otherwise fall back to an LLM-generated, reactive turn.
        """
        suggestions = suggestions or []
        if suggestions and random.random() < pickup_prob:
            picked = self.pick_suggestion(suggestions)
            if picked is not None:
                return picked

        messages = list(self._history)
        if hint:
            messages.append({"role": "system", "content": hint})
        else:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Schreib die nächste Nachricht im Chat — kurz, "
                        "wie tatsächlich getippt. Maximal 1–2 Sätze, "
                        "gerne nur ein Halbsatz mit '?'. Keine "
                        "Interview-Sprache.\n"
                        "Prüfe vorher kurz: hat die letzte Antwort "
                        "**alle drei Parteien** abgedeckt (Venus, Mars, "
                        "Saturn)? Wenn nein → frag nach der fehlenden "
                        "oder nur gestreiften Partei ('und Saturn?', "
                        "'mars konkreter?'). Wenn ja → vergleichende "
                        "Folgefrage ('unterschied bei X?', 'wer ist da "
                        "am strengsten?') oder Detail-Drilldown zu "
                        "einer Partei, sofern du zu den anderen schon "
                        "konkrete Positionen kennst.\n"
                        "Nicht zwei Detail-Turns hintereinander zur "
                        "selben Partei."
                    ),
                }
            )
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.85,
            max_tokens=140,
        )
        content = (resp.choices[0].message.content or "").strip()
        if not content:
            content = "Und was bedeutet das für mich konkret?"
        self._record_user_turn(content)
        return content

    async def wants_more(
        self,
        topic_label: str,
        min_done: int,
        max_remaining: int,
    ) -> bool:
        """Ask the persona whether it has another question worth asking.

        ``min_done`` enforces a floor — we don't bail out before the
        persona has had at least a minimum exposure. ``max_remaining``
        caps further turns. In between, the LLM decides yes/no based on
        the conversation so far.
        """
        if max_remaining <= 0:
            return False
        if min_done > 0:
            return True
        decision_messages = list(self._history) + [
            {
                "role": "system",
                "content": (
                    f"Du hast dich gerade über {topic_label} unterhalten. "
                    "Hast du auf Basis des bisherigen Chats spontan noch "
                    "eine konkrete Frage, die du wirklich stellen würdest? "
                    "Antworte AUSSCHLIESSLICH mit 'ja' oder 'nein'."
                ),
            }
        ]
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=decision_messages,
                temperature=0.4,
                max_tokens=4,
            )
            answer = (resp.choices[0].message.content or "").strip().lower()
            return answer.startswith("ja")
        except Exception:  # noqa: BLE001
            # On error, default to continuing so a transient API failure
            # doesn't truncate a session.
            return True

    async def estimate_elapsed_minutes(self) -> float:
        """Have the LLM estimate how long a real participant would have
        spent on this chat so far.

        The participant's time is dominated by reading the chatbot's
        replies (typical reading speed ~200 WpM) plus the cost of either
        clicking a suggested follow-up (~3 sec) or composing a fresh
        question (~15-30 sec). Used to cap the baseline run at a
        realistic 10-minute budget instead of a fixed turn count.
        """
        decision_messages = list(self._history) + [
            {
                "role": "system",
                "content": (
                    "Schätze, wie lange eine echte Studien-Versuchsperson "
                    "für den bisherigen Chatverlauf gebraucht hätte. "
                    "Berücksichtige:\n"
                    "- Bot-Antworten aufmerksam lesen (~200 Wörter/Min)\n"
                    "- kurz überlegen, was als Nächstes zu fragen wäre\n"
                    "- entweder eine vorgeschlagene Folgefrage anklicken "
                    "(~3-5 Sek) ODER selbst eine Frage tippen (~15-30 Sek)\n"
                    "Antworte AUSSCHLIESSLICH mit der geschätzten "
                    "Gesamtzeit in Minuten als Dezimalzahl, z.B. '3.5' "
                    "oder '7.0'. Keine Einheit, kein Text dahinter."
                ),
            }
        ]
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=decision_messages,
                temperature=0.2,
                max_tokens=8,
            )
            text = (resp.choices[0].message.content or "").strip()
            m = re.search(r"\d+(?:[.,]\d+)?", text)
            if not m:
                return 0.0
            return float(m.group().replace(",", "."))
        except Exception:  # noqa: BLE001
            return 0.0


# =============================================================================
# SSE client — yields parsed JSON events from a guided-exploration stream
# =============================================================================


async def sse_events(
    session: aiohttp.ClientSession,
    stream_url: str,
    client_id: str,
    idle_timeout: int,
) -> AsyncIterator[dict]:
    """
    Read SSE events from the guided-exploration stream URL.

    Yields dicts of the form ``{"type": <event_name>, ...payload}``.
    Closes when the underlying HTTP stream ends or idle timeout elapses.
    """
    headers = {"Accept": "text/event-stream"}
    params = {"client_id": client_id}
    timeout = aiohttp.ClientTimeout(total=None, sock_read=idle_timeout)
    async with session.get(
        stream_url,
        params=params,
        headers=headers,
        timeout=timeout,
    ) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise RuntimeError(
                f"SSE connect failed: {resp.status} {text[:200]}"
            )
        event_name: str | None = None
        data_buf: list[str] = []
        while True:
            raw = await resp.content.readline()
            if not raw:
                break
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if line == "":
                if data_buf:
                    payload = "\n".join(data_buf)
                    try:
                        parsed = json.loads(payload)
                    except json.JSONDecodeError:
                        parsed = {"type": event_name or "unknown", "raw": payload}
                    if isinstance(parsed, dict):
                        parsed.setdefault("type", event_name or parsed.get("type"))
                        yield parsed
                event_name = None
                data_buf = []
                continue
            if line.startswith(":"):
                continue
            if line.startswith("event:"):
                event_name = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_buf.append(line[len("data:"):].lstrip())


# =============================================================================
# SSE event queue — runs sse_events in a task and lets handlers wait by type
# =============================================================================


class EventBus:
    """
    Buffers SSE events and lets handlers ``wait_for(types, predicate)``.

    Avoids racing: events that arrived while the handler was busy are still
    matched on the next ``wait_for`` call.
    """

    def __init__(self) -> None:
        self._buffer: list[dict] = []
        self._cond = asyncio.Condition()
        self._closed = False
        self._error: BaseException | None = None
        self._task: asyncio.Task | None = None

    def start(self, source: AsyncIterator[dict]) -> None:
        self._task = asyncio.create_task(self._consume(source))

    async def _consume(self, source: AsyncIterator[dict]) -> None:
        try:
            async for event in source:
                async with self._cond:
                    self._buffer.append(event)
                    self._cond.notify_all()
        except BaseException as e:  # noqa: BLE001
            self._error = e
        finally:
            async with self._cond:
                self._closed = True
                self._cond.notify_all()

    async def wait_for(
        self,
        types: set[str],
        predicate=lambda ev: True,
        timeout: float = 120.0,
    ) -> dict:
        """Wait until an event matching ``types`` and ``predicate`` arrives."""
        deadline = asyncio.get_event_loop().time() + timeout
        async with self._cond:
            while True:
                # Search buffered events first.
                for i, ev in enumerate(self._buffer):
                    if ev.get("type") in types and predicate(ev):
                        del self._buffer[: i + 1]
                        return ev
                if self._closed:
                    if self._error:
                        raise self._error
                    raise TimeoutError(
                        f"SSE closed before any of {types} arrived"
                    )
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    raise TimeoutError(
                        f"Timed out waiting for {types}; "
                        f"buffer has {[e.get('type') for e in self._buffer]}"
                    )
                try:
                    await asyncio.wait_for(self._cond.wait(), timeout=remaining)
                except asyncio.TimeoutError:
                    pass

    async def close(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, BaseException):
                pass


# =============================================================================
# HTTP helpers
# =============================================================================


class StudyClient:
    """Thin wrapper around the exploration-study + guided-exploration HTTP APIs."""

    def __init__(self, http: aiohttp.ClientSession, base_url: str) -> None:
        self._http = http
        self._base = base_url.rstrip("/")
        self._es = f"{self._base}/api/v1/exploration-study"
        self._ge = f"{self._base}/api/v1/guided-exploration"

    async def _post(self, url: str, body: dict | None = None) -> dict:
        async with self._http.post(url, json=body or {}) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(f"POST {url} -> {resp.status} {text[:300]}")
            return json.loads(text) if text else {}

    async def _get(self, url: str) -> dict:
        async with self._http.get(url) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(f"GET {url} -> {resp.status} {text[:300]}")
            return json.loads(text) if text else {}

    # Lifecycle ---------------------------------------------------------------

    async def get_session_state(self, session_id: str) -> dict:
        return await self._get(f"{self._es}/sessions/{session_id}")

    async def submit_consent(self, session_id: str) -> dict:
        return await self._post(
            f"{self._es}/sessions/{session_id}/consent",
            {"consent_given": True},
        )

    async def complete_tutorial(self, session_id: str) -> dict:
        return await self._post(f"{self._es}/sessions/{session_id}/tutorial")

    async def start_task(self, session_id: str) -> dict:
        return await self._post(f"{self._es}/sessions/{session_id}/task/start")

    async def end_task(self, session_id: str) -> dict:
        return await self._post(f"{self._es}/sessions/{session_id}/task/end")

    async def submit_questionnaire(self, session_id: str) -> dict:
        body = {
            "cognitive_load": {
                "cl_icl_1": 4,
                "cl_icl_2": 4,
                "cl_ecl_1": 3,
                "cl_ecl_2": 3,
                "cl_ecl_3": 3,
                "cl_gcl_1": 5,
                "cl_gcl_2": 5,
            },
            "attention_check": 2,
            "ueq_s": {
                "obstructive_supportive": 5,
                "complicated_easy": 6,
                "inefficient_efficient": 5,
                "confusing_clear": 5,
                "boring_exciting": 4,
                "not_interesting_interesting": 5,
                "conventional_inventive": 5,
                "usual_leading_edge": 5,
            },
        }
        return await self._post(
            f"{self._es}/sessions/{session_id}/questionnaire", body
        )

    async def get_quiz(self, session_id: str) -> dict:
        return await self._get(f"{self._es}/sessions/{session_id}/quiz")

    async def submit_quiz(self, session_id: str, answers: list[dict]) -> dict:
        return await self._post(
            f"{self._es}/sessions/{session_id}/quiz",
            {"answers": answers},
        )

    async def submit_demographics(self, session_id: str) -> dict:
        body = {
            "age_range": "25-34",
            "gender": "diverse",
            "education": "hochschulabschluss",
            "political_interest": 4,
            "ai_chat_usage_frequency": "several_times_per_week",
        }
        return await self._post(
            f"{self._es}/sessions/{session_id}/demographics", body
        )

    # Guided exploration ------------------------------------------------------

    def stream_url(self, chat_id: str) -> str:
        return f"{self._ge}/sessions/{chat_id}/stream"

    async def send_message(
        self,
        chat_id: str,
        content: str,
        exploration_context: dict | None = None,
    ) -> dict:
        body: dict[str, Any] = {"content": content}
        if exploration_context:
            body["exploration_context"] = exploration_context
        return await self._post(
            f"{self._ge}/sessions/{chat_id}/message", body
        )

    async def submit_choice(
        self, chat_id: str, query_id: str, choice: str
    ) -> dict:
        return await self._post(
            f"{self._ge}/sessions/{chat_id}/choice",
            {"query_id": query_id, "choice": choice},
        )

    async def submit_direction_choice(
        self, chat_id: str, query_id: str, directions: list[dict]
    ) -> dict:
        return await self._post(
            f"{self._ge}/sessions/{chat_id}/direction-choice",
            {"query_id": query_id, "directions": directions},
        )

    async def navigate(
        self, chat_id: str, exploration_id: str, target_path: list[str]
    ) -> dict:
        return await self._post(
            f"{self._ge}/sessions/{chat_id}/explorations/{exploration_id}/navigate",
            {"target_path": target_path},
        )

    async def end_exploration(
        self, chat_id: str, exploration_id: str, generate_summary: bool = False
    ) -> dict:
        return await self._post(
            f"{self._ge}/sessions/{chat_id}/explorations/{exploration_id}/end",
            {"generate_summary": generate_summary},
        )


# =============================================================================
# Stream-end helpers — collect chunks, return final text
# =============================================================================


async def collect_stream(
    bus: EventBus,
    target_types: set[str],
    target_id: str | None = None,
    timeout: float = 120.0,
) -> str:
    """
    Wait for ``stream_end`` matching one of ``target_types`` (and optional id),
    accumulating ``stream_chunk`` text along the way.
    """
    chunks: dict[str, list[str]] = {}

    def is_match(ev: dict) -> bool:
        if ev.get("type") != "stream_end":
            return False
        if ev.get("target_type") not in target_types:
            return False
        if target_id is not None and ev.get("target_id") != target_id:
            return False
        return True

    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        remaining = max(1.0, deadline - asyncio.get_event_loop().time())
        ev = await bus.wait_for(
            {"stream_chunk", "stream_end", "error"},
            timeout=remaining,
        )
        if ev.get("type") == "error":
            raise RuntimeError(f"Stream error: {ev}")
        if ev.get("type") == "stream_chunk":
            if ev.get("target_type") in target_types:
                if target_id is None or ev.get("target_id") == target_id:
                    sid = ev.get("stream_id", "")
                    chunks.setdefault(sid, []).append(ev.get("chunk", ""))
            continue
        # stream_end
        if is_match(ev):
            sid = ev.get("stream_id", "")
            return "".join(chunks.get(sid, []))


# =============================================================================
# Baseline handler
# =============================================================================


async def run_baseline(
    client: StudyClient,
    bus: EventBus,
    persona: PersonaChat,
    chat_id: str,
    report: SessionReport,
    cfg: SimConfig,
) -> None:
    """Plain message loop — no exploration option.

    Each turn we ask the persona's LLM to estimate how many minutes a
    real participant would have spent on the chat so far (reading the
    bot's replies + composing or clicking the next question). The loop
    runs until that estimate hits ``cfg.baseline_budget_minutes`` (~10),
    which is what real participants face under the 600s task cap. A
    safety hard-cap (``cfg.baseline_max_turns``) prevents runaway loops
    when the LLM under-estimates.
    """
    last_suggestions: list[str] = []
    for turn in range(cfg.baseline_max_turns):
        question = await persona.next_user_turn(
            suggestions=last_suggestions,
            pickup_prob=cfg.suggestion_pickup_prob,
        )
        report.user_messages.append(question)
        logger.info(f"[{report.session_id[:8]}] baseline turn {turn+1}: {question[:80]}")
        await client.send_message(chat_id, question)
        # Baseline replies arrive as quick_summary or chat_message events.
        # Watch for stream_end of those targets, plus the events themselves.
        ev = await bus.wait_for(
            {"quick_summary", "chat_message", "stream_end", "error"},
            timeout=120.0,
        )
        text = ""
        last_suggestions = []
        if ev.get("type") == "error":
            raise RuntimeError(f"Backend error: {ev}")
        if ev.get("type") == "quick_summary":
            text = ev.get("text", "")
            last_suggestions = ev.get("suggested_questions", []) or []
        elif ev.get("type") == "chat_message":
            text = ev.get("content", "")
            last_suggestions = ev.get("suggested_questions", []) or []
        elif ev.get("type") == "stream_end":
            # In case the chunked path was taken; nothing accumulated yet.
            text = ""
        # Drain trailing stream_end so the next iteration starts clean.
        try:
            await bus.wait_for(
                {"stream_end"},
                lambda e: e.get("target_type") in {"quick_summary", "chat_message", "system_message"},
                timeout=10.0,
            )
        except TimeoutError:
            pass
        if text:
            persona.add_assistant(text)
            report.assistant_messages.append(text)

        # Stop when the persona's estimated elapsed time hits the budget.
        elapsed = await persona.estimate_elapsed_minutes()
        logger.info(
            f"[{report.session_id[:8]}] baseline turn {turn+1} done "
            f"— elapsed estimate {elapsed:.1f} min "
            f"(budget {cfg.baseline_budget_minutes:.1f})"
        )
        if elapsed >= cfg.baseline_budget_minutes:
            break


# =============================================================================
# Guided handler
# =============================================================================


async def run_guided(
    client: StudyClient,
    bus: EventBus,
    persona: PersonaChat,
    chat_id: str,
    report: SessionReport,
    cfg: SimConfig,
) -> None:
    """
    Guided session: fire an initial main-chat question to get topic
    directions, walk every leaf with two follow-ups each, then ask one
    more main-chat question at the end.
    """
    # Phase 1 — initial main-chat question kicks off exploration.
    initial_q = await persona.next_user_turn(
        suggestions=None,
        hint=(
            "Schreib deine erste kurze Frage in den Chat. Einstieg ins "
            "Themenfeld, der **alle drei Parteien** abdeckt — z.B. 'was "
            "sagen venus, mars und saturn zu …?' oder 'wie unterscheiden "
            "die drei sich bei …?'. Locker und knapp, kein Interview-Stil."
        ),
        pickup_prob=0.0,
    )
    report.user_messages.append(initial_q)
    logger.info(f"[{report.session_id[:8]}] guided initial: {initial_q[:80]}")
    await client.send_message(chat_id, initial_q)

    # Backend offers a choice prompt for guided sessions.
    ev = await bus.wait_for({"choice_prompt", "quick_summary", "error"}, timeout=120.0)
    if ev.get("type") == "error":
        raise RuntimeError(f"Backend error before choice: {ev}")
    if ev.get("type") == "quick_summary":
        # Backend decided this didn't need exploration. Treat like baseline turn.
        text = ev.get("text", "")
        if text:
            persona.add_assistant(text)
            report.assistant_messages.append(text)
        await _final_main_chat_question(client, bus, persona, chat_id, report)
        return

    query_id = ev.get("query_id")
    if not query_id:
        raise RuntimeError(f"choice_prompt missing query_id: {ev}")
    await client.submit_choice(chat_id, query_id, "explore")

    # Phase 2 — topic directions multi-select.
    directions_ev = await bus.wait_for({"topic_directions", "error"}, timeout=120.0)
    if directions_ev.get("type") == "error":
        raise RuntimeError(f"Backend error after choice: {directions_ev}")
    directions = directions_ev.get("directions", [])
    if not directions:
        raise RuntimeError(f"topic_directions had no directions: {directions_ev}")
    # Pick all directions to maximize tree breadth (matches a curious user).
    selected = [{"id": d["id"], "name": d["name"]} for d in directions]
    await client.submit_direction_choice(
        chat_id, directions_ev["query_id"], selected
    )

    # Phase 3 — wait for the tree, then for ready (knowledge base loaded).
    tree_ev = await bus.wait_for({"topic_tree", "error"}, timeout=180.0)
    if tree_ev.get("type") == "error":
        raise RuntimeError(f"Backend error building tree: {tree_ev}")
    tree = tree_ev.get("tree") or {}
    exploration_id = tree_ev.get("exploration_id") or tree.get("exploration_id")
    if not exploration_id:
        raise RuntimeError("topic_tree missing exploration_id")

    await bus.wait_for({"exploration_ready", "error"}, timeout=180.0)

    leaves = _collect_leaves(tree.get("root") or {})
    logger.info(
        f"[{report.session_id[:8]}] guided tree has {len(leaves)} leaves"
    )

    # Phase 4 — walk every leaf. Per-leaf follow-up count varies, and the
    # persona prefers the chatbot's own ``suggested_questions`` when offered.
    topic_label = _topic_label(report.topic)
    for leaf in leaves:
        leaf_id = leaf["id"]
        leaf_name = leaf.get("name") or leaf_id
        report.leaves_visited.append(leaf_id)
        logger.info(
            f"[{report.session_id[:8]}] navigate to leaf {leaf_id} ({leaf_name})"
        )

        await client.navigate(chat_id, exploration_id, [leaf_id])
        opened = await bus.wait_for(
            {"conversation_opened", "error"}, timeout=180.0
        )
        if opened.get("type") == "error":
            raise RuntimeError(f"navigate error: {opened}")

        # The conversation_opened event itself carries the first batch of
        # suggested follow-up questions for this leaf.
        last_suggestions: list[str] = list(
            opened.get("suggested_questions", []) or []
        )

        # Drain initial_content stream so the persona sees it before asking.
        try:
            initial_text = await collect_stream(
                bus, {"initial_content"}, target_id=leaf_id, timeout=180.0
            )
        except TimeoutError:
            initial_text = ""
        if initial_text:
            persona.add_assistant(f"[{leaf_name}] {initial_text}")
            report.assistant_messages.append(initial_text)

        target_followups = random.randint(
            cfg.followups_per_leaf_min, cfg.followups_per_leaf_max
        )
        for fu in range(target_followups):
            if fu >= cfg.followups_per_leaf_min:
                keep_going = await persona.wants_more(
                    f"das Unterthema '{leaf_name}'",
                    min_done=cfg.followups_per_leaf_min - fu,
                    max_remaining=target_followups - fu,
                )
                if not keep_going:
                    logger.info(
                        f"[{report.session_id[:8]}] leaf {leaf_id} done after "
                        f"{fu} follow-up(s) (target was {target_followups})"
                    )
                    break
            q = await persona.next_user_turn(
                suggestions=last_suggestions,
                pickup_prob=cfg.suggestion_pickup_prob,
                hint=(
                    f"Du bist im Unterthema '{leaf_name}'. Bevor du "
                    "Detail-Drilldowns machst: stell sicher, dass du in "
                    "diesem Unterthema die Position **aller drei** "
                    "Parteien (Venus, Mars, Saturn) kennst. Wenn eine "
                    "fehlt → 'und Saturn dazu?' / 'wie sieht das mars?'. "
                    "Erst dann nachhaken oder vergleichen — locker, "
                    "knapp, wie tatsächlich getippt."
                ),
            )
            report.user_messages.append(q)
            logger.info(
                f"[{report.session_id[:8]}] leaf {leaf_id} fu{fu+1}: {q[:80]}"
            )
            await client.send_message(
                chat_id,
                q,
                exploration_context={
                    "exploration_id": exploration_id,
                    "leaf_id": leaf_id,
                },
            )
            try:
                reply = await collect_stream(
                    bus, {"followup"}, target_id=leaf_id, timeout=180.0
                )
            except TimeoutError as e:
                logger.warning(
                    f"[{report.session_id[:8]}] follow-up timed out: {e}"
                )
                reply = ""
            if reply:
                persona.add_assistant(reply)
                report.assistant_messages.append(reply)
            # The conversation_message event carrying fresh suggestions
            # arrives shortly after the follow-up stream ends.
            try:
                msg_ev = await bus.wait_for(
                    {"conversation_message"}, timeout=15.0
                )
                last_suggestions = list(
                    msg_ev.get("suggested_questions", []) or []
                )
            except TimeoutError:
                last_suggestions = []

    # Phase 5 — close exploration (no closing summary, keeps it short).
    try:
        await client.end_exploration(chat_id, exploration_id, generate_summary=False)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"end_exploration failed: {e}")

    # Phase 6 — one more main-chat question after the exploration wraps.
    await _final_main_chat_question(client, bus, persona, chat_id, report)


async def _final_main_chat_question(
    client: StudyClient,
    bus: EventBus,
    persona: PersonaChat,
    chat_id: str,
    report: SessionReport,
) -> None:
    """Single closing main-chat question after the exploration completes."""
    q = await persona.next_user_turn(
        suggestions=None,
        hint=(
            "Stell zum Abschluss noch eine kurze Frage im Hauptchat, die "
            "**alle drei Parteien** beim Thema kurz vergleicht — z.B. "
            "größter Unterschied zwischen Venus, Mars und Saturn, oder "
            "ein noch nicht gestreifter Aspekt für alle drei. Locker und "
            "knapp, kein Interview-Ton."
        ),
        pickup_prob=0.0,
    )
    report.user_messages.append(q)
    logger.info(f"[{report.session_id[:8]}] guided final: {q[:80]}")
    await client.send_message(chat_id, q)
    try:
        ev = await bus.wait_for(
            {"quick_summary", "chat_message", "choice_prompt", "error"},
            timeout=120.0,
        )
    except TimeoutError:
        return
    if ev.get("type") == "choice_prompt":
        # The user spec says "ask one question" — accept any backend response,
        # so just opt for summary to avoid another full exploration.
        await client.submit_choice(chat_id, ev["query_id"], "summary")
        try:
            ev2 = await bus.wait_for(
                {"quick_summary", "chat_message", "error"}, timeout=120.0
            )
        except TimeoutError:
            return
        if ev2.get("type") in ("quick_summary", "chat_message"):
            text = ev2.get("text") or ev2.get("content", "")
            if text:
                persona.add_assistant(text)
                report.assistant_messages.append(text)
    elif ev.get("type") in ("quick_summary", "chat_message"):
        text = ev.get("text") or ev.get("content", "")
        if text:
            persona.add_assistant(text)
            report.assistant_messages.append(text)


def _collect_leaves(root: dict) -> list[dict]:
    """Walk the JSON-form tree and return every leaf node."""
    if not root:
        return []
    children = root.get("children") or []
    if not children:
        return [root]
    out: list[dict] = []
    for c in children:
        out.extend(_collect_leaves(c))
    return out


# =============================================================================
# Per-session orchestration
# =============================================================================


async def run_one_session(
    session_id: str,
    cfg: SimConfig,
    semaphore: asyncio.Semaphore,
) -> SessionReport:
    """Drive a single session through its full lifecycle."""
    report = SessionReport(
        session_id=session_id,
        group="?",
        system="?",
        topic="?",
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    async with semaphore:
        try:
            timeout = aiohttp.ClientTimeout(total=None, sock_connect=30, sock_read=180)
            async with aiohttp.ClientSession(timeout=timeout) as http:
                client = StudyClient(http, cfg.base_url)

                state_resp = await client.get_session_state(session_id)
                state = state_resp.get("state")
                report.group = state_resp.get("group", "?")
                report.system = state_resp.get("current_system") or state_resp.get(
                    "current_condition"
                ) or "?"
                report.topic = state_resp.get("current_topic") or "?"

                if state == StudyState.COMPLETE.value:
                    report.error = "session already complete"
                    return report

                # Walk through pre-task lifecycle steps.
                if state == StudyState.CONSENT.value:
                    await client.submit_consent(session_id)
                    state = StudyState.TUTORIAL.value
                if state == StudyState.TUTORIAL.value:
                    await client.complete_tutorial(session_id)
                    state = StudyState.TASK.value

                if state != StudyState.TASK.value:
                    report.error = f"session not in TASK state: {state}"
                    return report

                start_resp = await client.start_task(session_id)
                chat_id = start_resp["chat_id"]
                report.chat_id = chat_id
                # Override topic/system from start response (canonical source).
                report.topic = start_resp.get("topic", report.topic)
                report.system = start_resp.get("system", report.system)

                # Open SSE stream and start the conversation handler.
                bus = EventBus()
                stream_url = client.stream_url(chat_id)
                client_id = f"sim-{uuid.uuid4().hex[:8]}"
                events_iter = sse_events(
                    http, stream_url, client_id, cfg.sse_idle_timeout_seconds
                )
                bus.start(events_iter)

                # Backend sends ``connected`` immediately; consume so we don't
                # match it later as some other type's no-op.
                try:
                    await bus.wait_for({"connected"}, timeout=15.0)
                except TimeoutError:
                    logger.warning(f"[{session_id[:8]}] no connected event")

                persona = PersonaChat(cfg.openai_model, report.topic)

                try:
                    if report.system == SystemType.GUIDED.value:
                        await run_guided(
                            client, bus, persona, chat_id, report, cfg
                        )
                    else:
                        await run_baseline(
                            client, bus, persona, chat_id, report, cfg
                        )
                finally:
                    await bus.close()

                # End the task — triggers quiz generation in the background.
                await client.end_task(session_id)

                # Submit the questionnaire so the session can move to QUIZ.
                await client.submit_questionnaire(session_id)

                # Poll until quiz is READY or FAILED (or timeout).
                quiz_resp = await _poll_quiz(client, session_id, cfg)
                report.quiz_status = quiz_resp.get("status")
                report.quiz_error = quiz_resp.get("error_message")
                if quiz_resp.get("is_ready"):
                    questions = quiz_resp.get("questions") or []
                    report.quiz_questions = questions
                    # Submit random answers so the lifecycle can advance.
                    answers = [
                        {
                            "question_id": q["id"],
                            "selected_index": random.randint(0, 4),
                            "response_time_ms": 1500,
                        }
                        for q in questions
                    ]
                    if answers:
                        await client.submit_quiz(session_id, answers)
                        await client.submit_demographics(session_id)

        except Exception as e:  # noqa: BLE001
            logger.exception(f"[{session_id[:8]}] failed: {e}")
            report.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        finally:
            report.finished_at = datetime.now(timezone.utc).isoformat()
            _write_report(cfg.output_dir, report)
    return report


async def _poll_quiz(
    client: StudyClient, session_id: str, cfg: SimConfig
) -> dict:
    deadline = time.time() + cfg.quiz_poll_timeout_seconds
    last: dict = {}
    while time.time() < deadline:
        last = await client.get_quiz(session_id)
        status = last.get("status")
        if last.get("is_ready") or status in (
            QuizStatus.READY.value,
            QuizStatus.FAILED.value,
        ):
            return last
        await asyncio.sleep(cfg.quiz_poll_interval_seconds)
    return last


def _write_report(output_dir: Path, report: SessionReport) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{report.session_id}.json"
    path.write_text(
        json.dumps(report.__dict__, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


# =============================================================================
# Top-level runner
# =============================================================================


async def list_eligible_sessions(study_id: str) -> list[tuple[str, str, str, str]]:
    """
    Return ``(session_id, group, system, topic)`` for sessions in the given
    study that are eligible to run (state CONSENT or TASK, not yet complete).
    """
    session_repo = get_session_repository()
    study_repo = get_study_repository()
    study = await study_repo.get_study(study_id)
    if not study:
        raise SystemExit(f"Study not found: {study_id}")
    sessions = await session_repo.list_sessions_for_study(study_id)
    out: list[tuple[str, str, str, str]] = []
    for s in sessions:
        state = s.state.value if hasattr(s.state, "value") else str(s.state)
        if state in (
            StudyState.COMPLETE.value,
            StudyState.ABANDONED.value,
        ):
            continue
        cond = s.condition
        system = cond.system.value if hasattr(cond.system, "value") else str(cond.system)
        out.append((s.id, s.group, system, cond.topic))
    return out


async def main_async(args: argparse.Namespace) -> None:
    cfg = SimConfig(
        base_url=args.base_url,
        output_dir=Path(args.output_dir),
        concurrency=args.concurrency,
        baseline_budget_minutes=args.baseline_budget_minutes,
        baseline_max_turns=args.baseline_max_turns,
        followups_per_leaf_min=args.followups_per_leaf_min,
        followups_per_leaf_max=args.followups_per_leaf_max,
        suggestion_pickup_prob=args.suggestion_pickup_prob,
        openai_model=args.openai_model,
    )

    if args.session_ids_file:
        ids = [
            line.strip()
            for line in Path(args.session_ids_file).read_text().splitlines()
            if line.strip()
        ]
        # We still need group/system/topic for reporting; fetch via API later.
        targets = [(sid, "?", "?", "?") for sid in ids]
    elif args.study_id:
        targets = await list_eligible_sessions(args.study_id)
    else:
        raise SystemExit("Provide either --study-id or --session-ids-file")

    if args.limit and args.limit > 0:
        targets = targets[: args.limit]

    if not targets:
        print("No eligible sessions to simulate.")
        return

    print(
        f"Simulating {len(targets)} session(s) with concurrency={cfg.concurrency} "
        f"against {cfg.base_url}"
    )
    for sid, group, system, topic in targets:
        print(f"  {sid}  group={group}  system={system}  topic={topic}")

    sem = asyncio.Semaphore(cfg.concurrency)
    coros = [run_one_session(sid, cfg, sem) for sid, _, _, _ in targets]
    reports = await asyncio.gather(*coros, return_exceptions=False)

    _print_summary(reports, cfg)


def _print_summary(reports: list[SessionReport], cfg: SimConfig) -> None:
    print("\n========== Summary ==========")
    print(f"Total sessions: {len(reports)}")
    by_status: dict[str, int] = {}
    by_system: dict[str, dict[str, int]] = {}
    failures: list[SessionReport] = []
    for r in reports:
        status = r.quiz_status or ("error" if r.error else "missing")
        by_status[status] = by_status.get(status, 0) + 1
        by_system.setdefault(r.system, {})
        by_system[r.system][status] = by_system[r.system].get(status, 0) + 1
        if r.error or status not in ("ready",):
            failures.append(r)
    print("Quiz status counts:")
    for k, v in sorted(by_status.items()):
        print(f"  {k}: {v}")
    print("By system:")
    for sys_name, counts in by_system.items():
        print(f"  {sys_name}: {counts}")
    if failures:
        print("\nFailed/non-ready sessions:")
        for r in failures:
            print(
                f"  {r.session_id} system={r.system} status={r.quiz_status} "
                f"error={r.error or r.quiz_error or '-'}"
            )
    print(f"\nReports written to: {cfg.output_dir.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="End-to-end simulator for the exploration study"
    )
    parser.add_argument(
        "--study-id",
        help="Study ID to enumerate sessions from (uses Firebase directly)",
    )
    parser.add_argument(
        "--session-ids-file",
        help="Optional file with session IDs (one per line)",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("STUDY_API_BASE_URL", "http://localhost:8080"),
        help="Backend base URL",
    )
    parser.add_argument(
        "--concurrency", type=int, default=3, help="Parallel sessions"
    )
    parser.add_argument(
        "--baseline-budget-minutes",
        type=float,
        default=10.0,
        help=(
            "Baseline session runs until the persona's LLM-estimated "
            "elapsed minutes hit this budget (default 10, matching the "
            "600s task cap)."
        ),
    )
    parser.add_argument(
        "--baseline-max-turns",
        type=int,
        default=25,
        help="Safety hard-cap on baseline turns if the estimate stays low.",
    )
    parser.add_argument(
        "--followups-per-leaf-min",
        type=int,
        default=1,
        help="Minimum follow-ups per leaf in guided sessions",
    )
    parser.add_argument(
        "--followups-per-leaf-max",
        type=int,
        default=3,
        help="Maximum follow-ups per leaf in guided sessions",
    )
    parser.add_argument(
        "--suggestion-pickup-prob",
        type=float,
        default=0.85,
        help=(
            "Probability of picking from the chatbot's suggested follow-ups "
            "when offered (vs. generating a fresh persona-driven turn)."
        ),
    )
    parser.add_argument(
        "--openai-model",
        default=os.getenv("SIMULATOR_OPENAI_MODEL", "gpt-4o-mini"),
        help="OpenAI model for the simulated participant",
    )
    parser.add_argument(
        "--output-dir",
        default="simulate_results",
        help="Where to write per-session JSON reports",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of sessions (0 = all)",
    )
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY must be set in the environment")

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()

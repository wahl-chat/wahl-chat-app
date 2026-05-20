"""Behavioral integrity telemetry models.

Captures lightweight, content-free behavioral signals across the study
screens (task, quiz, questionnaire, …) so the admin can surface possible
external-aid use — e.g. a participant tabbing out to look up quiz answers.

Privacy by design: only event *metadata* is stored — never copied/pasted
text or any other page content. A ``paste`` event records the length of
the pasted text, not the text itself.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BrowserProfile(BaseModel):
    """One-shot client/device fingerprint, captured once per session.

    Standard, non-invasive ``navigator``/``screen`` fields. Useful for
    spotting e.g. mobile vs desktop, or the same device across sessions.
    """

    model_config = {"extra": "ignore"}

    user_agent: str | None = None
    platform: str | None = None
    languages: list[str] = Field(default_factory=list)
    timezone: str | None = None
    screen_width: int | None = None
    screen_height: int | None = None
    viewport_width: int | None = None
    viewport_height: int | None = None
    device_pixel_ratio: float | None = None
    hardware_concurrency: int | None = None
    device_memory: float | None = None
    max_touch_points: int | None = None


class TelemetryEvent(BaseModel):
    """A single behavioral event.

    Kept deliberately generic so the client can add event types without a
    backend change. ``value`` is an event-specific numeric payload (paste
    length, cursor-jump distance in px, …).
    """

    model_config = {"extra": "ignore"}

    screen: str = Field(..., description="Study screen, e.g. 'quiz', 'task'.")
    type: str = Field(
        ...,
        description=(
            "Event type: visibility_hidden/visible, window_blur/focus, "
            "copy/cut/paste, pointer_leave/enter, cursor_jump, "
            "screen_enter/exit, item_timing."
        ),
    )
    ts: int = Field(..., description="Client event time, epoch milliseconds.")
    duration_ms: int | None = Field(
        default=None,
        description="Elapsed time for span events (e.g. ms spent hidden).",
    )
    item_id: str | None = Field(
        default=None,
        description="Active item/question id when the event fired, if any.",
    )
    value: float | None = Field(
        default=None,
        description="Event-specific numeric payload (paste length, jump px).",
    )


class TelemetryBatchRequest(BaseModel):
    """A flushed batch of telemetry from the client.

    ``browser_profile`` is sent on the first flush of a session and omitted
    afterwards. Lenient on purpose: a malformed batch should never break the
    participant's flow.
    """

    model_config = {"extra": "ignore"}

    browser_profile: BrowserProfile | None = None
    events: list[TelemetryEvent] = Field(default_factory=list)


class TelemetryBatch(TelemetryBatchRequest):
    """A stored batch — the request plus the server receive time."""

    received_at: datetime

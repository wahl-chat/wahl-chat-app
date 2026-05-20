/**
 * Behavioral integrity telemetry collector (client side).
 *
 * Buffers lightweight, content-free behavioral events across study screens
 * (task, quiz, questionnaire, …) and flushes them to the backend in batches.
 * Used by the admin to surface possible external-aid use — e.g. a participant
 * tabbing out to look up quiz answers.
 *
 * Privacy by design: only event *metadata* is recorded. A `paste` event keeps
 * the length of the pasted text, never the text itself. Nothing here captures
 * page content, keystrokes, or clipboard contents.
 *
 * Dependency-free on purpose: no third-party analytics SDK, no cookies.
 */

'use client';

import { keysToSnakeCase } from '@/modules/guided-exploration/utils/case-conversion';

const API_BASE = '/api/v1/exploration-study/sessions';
const FLUSH_INTERVAL_MS = 15_000;
const MAX_BUFFER = 40;

export type TelemetryEventType =
  | 'screen_enter'
  | 'screen_exit'
  | 'visibility_hidden'
  | 'visibility_visible'
  | 'window_blur'
  | 'window_focus'
  | 'copy'
  | 'cut'
  | 'paste'
  | 'pointer_leave'
  | 'pointer_enter'
  | 'cursor_jump'
  | 'item_timing';

export interface TelemetryEventInput {
  screen: string;
  type: TelemetryEventType;
  /** Defaults to `Date.now()` when omitted. */
  ts?: number;
  /** Elapsed time for span events (e.g. ms spent hidden, time on item). */
  durationMs?: number;
  /** Active item/question id when the event fired, if any. */
  itemId?: string;
  /** Event-specific numeric payload (paste length, cursor-jump px). */
  value?: number;
}

interface BufferedEvent {
  screen: string;
  type: string;
  ts: number;
  durationMs?: number;
  itemId?: string;
  value?: number;
}

interface BrowserProfile {
  userAgent?: string;
  platform?: string;
  languages: string[];
  timezone?: string;
  screenWidth?: number;
  screenHeight?: number;
  viewportWidth?: number;
  viewportHeight?: number;
  devicePixelRatio?: number;
  hardwareConcurrency?: number;
  deviceMemory?: number;
  maxTouchPoints?: number;
}

function captureBrowserProfile(): BrowserProfile {
  const nav = navigator as Navigator & {
    deviceMemory?: number;
  };
  let timezone: string | undefined;
  try {
    timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  } catch {
    timezone = undefined;
  }
  return {
    userAgent: nav.userAgent,
    platform: nav.platform,
    languages: nav.languages ? [...nav.languages] : [],
    timezone,
    screenWidth: window.screen?.width,
    screenHeight: window.screen?.height,
    viewportWidth: window.innerWidth,
    viewportHeight: window.innerHeight,
    devicePixelRatio: window.devicePixelRatio,
    hardwareConcurrency: nav.hardwareConcurrency,
    deviceMemory: nav.deviceMemory,
    maxTouchPoints: nav.maxTouchPoints,
  };
}

/**
 * Per-session telemetry buffer. Use {@link getTelemetry} to obtain the shared
 * instance for a session rather than constructing this directly.
 */
class StudyTelemetry {
  private readonly sessionId: string;
  private buffer: BufferedEvent[] = [];
  private profileSent = false;
  private flushTimer: ReturnType<typeof setInterval> | null = null;
  private unloadHandlersBound = false;

  constructor(sessionId: string) {
    this.sessionId = sessionId;
  }

  /** Record an event. Auto-flushes when the buffer grows large. */
  record(event: TelemetryEventInput): void {
    this.buffer.push({
      screen: event.screen,
      type: event.type,
      ts: event.ts ?? Date.now(),
      durationMs: event.durationMs,
      itemId: event.itemId,
      value: event.value,
    });
    this.ensureStarted();
    if (this.buffer.length >= MAX_BUFFER) {
      void this.flush();
    }
  }

  /**
   * Begin periodic flushing and bind unload handlers. Idempotent — safe to
   * call from every screen that mounts.
   */
  ensureStarted(): void {
    if (typeof window === 'undefined') return;
    if (!this.flushTimer) {
      this.flushTimer = setInterval(() => {
        void this.flush();
      }, FLUSH_INTERVAL_MS);
    }
    if (!this.unloadHandlersBound) {
      this.unloadHandlersBound = true;
      // `pagehide` is the most reliable unload signal across browsers
      // (incl. bfcache). `visibilitychange → hidden` covers tab switches and
      // mobile app-switching where `pagehide` may not fire.
      window.addEventListener('pagehide', this.handleUnload);
      document.addEventListener('visibilitychange', this.handleVisibilityFlush);
    }
  }

  private readonly handleUnload = (): void => {
    void this.flush(true);
  };

  private readonly handleVisibilityFlush = (): void => {
    if (document.visibilityState === 'hidden') {
      void this.flush(true);
    }
  };

  /**
   * Send buffered events. When `keepaliveMode` is set the request is allowed
   * to outlive the page (used on unload). Fire-and-forget: failures are
   * swallowed so telemetry never disrupts the participant.
   */
  async flush(keepaliveMode = false): Promise<void> {
    if (this.buffer.length === 0 && this.profileSent) return;
    if (this.buffer.length === 0 && !this.profileSent && !keepaliveMode) {
      // Nothing to send yet and no profile pressure — wait for real events.
      return;
    }

    const events = this.buffer;
    this.buffer = [];

    const payload: {
      browserProfile?: BrowserProfile;
      events: BufferedEvent[];
    } = { events };
    if (!this.profileSent) {
      payload.browserProfile = captureBrowserProfile();
    }

    if (events.length === 0 && !payload.browserProfile) return;

    try {
      const response = await fetch(`${API_BASE}/${this.sessionId}/telemetry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(keysToSnakeCase(payload)),
        keepalive: keepaliveMode,
      });
      if (response.ok && payload.browserProfile) {
        this.profileSent = true;
      }
      if (!response.ok) {
        // Re-buffer so the events get another chance on the next flush.
        this.buffer = events.concat(this.buffer);
      }
    } catch {
      this.buffer = events.concat(this.buffer);
    }
  }
}

const registry = new Map<string, StudyTelemetry>();

/** Return the shared telemetry collector for a session, creating it once. */
export function getTelemetry(sessionId: string): StudyTelemetry {
  let instance = registry.get(sessionId);
  if (!instance) {
    instance = new StudyTelemetry(sessionId);
    registry.set(sessionId, instance);
  }
  return instance;
}

export type { StudyTelemetry };

'use client';

import {
  type TelemetryEventInput,
  getTelemetry,
} from '@/modules/exploration-study/services/telemetry';
import { useCallback, useEffect, useRef } from 'react';

export interface UseScreenTelemetryOptions {
  /**
   * Resolver for the item/question currently in focus. Tagged onto behavioral
   * events (copy, visibility, …) so the admin can see *which* quiz item the
   * participant tabbed away from. Read lazily at event time.
   */
  getItemId?: () => string | undefined;
  /** Detect large instantaneous cursor jumps (default true). */
  trackCursorJumps?: boolean;
  /** Disable all tracking (e.g. before the screen is ready). */
  enabled?: boolean;
}

export interface UseScreenTelemetryReturn {
  /** Record an arbitrary event tagged with this screen. */
  record: (event: Omit<TelemetryEventInput, 'screen'>) => void;
  /** Convenience for per-item dwell timing (e.g. ms spent on a question). */
  recordItemTiming: (itemId: string, durationMs: number) => void;
}

// A genuine pointer teleport (e.g. returning from another window/monitor)
// shows up as a single mousemove delta well beyond normal hand motion.
const CURSOR_JUMP_PX = 700;
// Don't log more than one jump per second — avoids floods on fast motion.
const CURSOR_JUMP_THROTTLE_MS = 1000;

/**
 * Wire behavioral integrity listeners for the lifetime of a study screen.
 *
 * Records `screen_enter`/`screen_exit`, tab/window focus changes, copy/cut/
 * paste (paste keeps length only), pointer leaving/entering the viewport, and
 * large cursor jumps. All events are buffered and flushed by the shared
 * per-session collector. No-op during SSR.
 */
export function useScreenTelemetry(
  sessionId: string,
  screen: string,
  options: UseScreenTelemetryOptions = {},
): UseScreenTelemetryReturn {
  const { getItemId, trackCursorJumps = true, enabled = true } = options;

  // Keep the latest option callbacks in refs so the effect doesn't re-bind
  // listeners on every render.
  const getItemIdRef = useRef(getItemId);
  getItemIdRef.current = getItemId;

  const record = useCallback(
    (event: Omit<TelemetryEventInput, 'screen'>) => {
      if (!sessionId) return;
      getTelemetry(sessionId).record({
        screen,
        ...event,
        itemId: event.itemId ?? getItemIdRef.current?.(),
      });
    },
    [sessionId, screen],
  );

  const recordItemTiming = useCallback(
    (itemId: string, durationMs: number) => {
      if (!sessionId) return;
      getTelemetry(sessionId).record({
        screen,
        type: 'item_timing',
        itemId,
        durationMs,
      });
    },
    [sessionId, screen],
  );

  useEffect(() => {
    if (!enabled || !sessionId || typeof window === 'undefined') return;

    const telemetry = getTelemetry(sessionId);
    telemetry.ensureStarted();

    const itemId = () => getItemIdRef.current?.();
    const push = (event: Omit<TelemetryEventInput, 'screen'>) => {
      telemetry.record({ screen, ...event, itemId: event.itemId ?? itemId() });
    };

    const enterTs = Date.now();
    push({ type: 'screen_enter', ts: enterTs });

    let hiddenAt: number | null = null;
    const onVisibility = () => {
      if (document.visibilityState === 'hidden') {
        hiddenAt = Date.now();
        push({ type: 'visibility_hidden', ts: hiddenAt });
      } else {
        push({
          type: 'visibility_visible',
          durationMs: hiddenAt ? Date.now() - hiddenAt : undefined,
        });
        hiddenAt = null;
      }
    };

    let blurredAt: number | null = null;
    const onBlur = () => {
      blurredAt = Date.now();
      push({ type: 'window_blur', ts: blurredAt });
    };
    const onFocus = () => {
      push({
        type: 'window_focus',
        durationMs: blurredAt ? Date.now() - blurredAt : undefined,
      });
      blurredAt = null;
    };

    const onCopy = () => push({ type: 'copy' });
    const onCut = () => push({ type: 'cut' });
    const onPaste = (e: ClipboardEvent) => {
      // Length only — never the pasted text.
      const length = e.clipboardData?.getData('text')?.length;
      push({ type: 'paste', value: length });
    };

    // Cursor leaving / re-entering the viewport.
    const onPointerLeave = () => push({ type: 'pointer_leave' });
    const onPointerEnter = () => push({ type: 'pointer_enter' });

    // Large instantaneous cursor jumps.
    let lastX: number | null = null;
    let lastY: number | null = null;
    let lastJumpTs = 0;
    const onMouseMove = (e: MouseEvent) => {
      if (lastX !== null && lastY !== null) {
        const dist = Math.hypot(e.clientX - lastX, e.clientY - lastY);
        const now = Date.now();
        if (
          dist >= CURSOR_JUMP_PX &&
          now - lastJumpTs >= CURSOR_JUMP_THROTTLE_MS
        ) {
          lastJumpTs = now;
          push({ type: 'cursor_jump', value: Math.round(dist) });
        }
      }
      lastX = e.clientX;
      lastY = e.clientY;
    };

    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('blur', onBlur);
    window.addEventListener('focus', onFocus);
    document.addEventListener('copy', onCopy);
    document.addEventListener('cut', onCut);
    document.addEventListener('paste', onPaste);
    document.documentElement.addEventListener('mouseleave', onPointerLeave);
    document.documentElement.addEventListener('mouseenter', onPointerEnter);
    if (trackCursorJumps) {
      window.addEventListener('mousemove', onMouseMove);
    }

    return () => {
      push({ type: 'screen_exit', durationMs: Date.now() - enterTs });
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('blur', onBlur);
      window.removeEventListener('focus', onFocus);
      document.removeEventListener('copy', onCopy);
      document.removeEventListener('cut', onCut);
      document.removeEventListener('paste', onPaste);
      document.documentElement.removeEventListener(
        'mouseleave',
        onPointerLeave,
      );
      document.documentElement.removeEventListener(
        'mouseenter',
        onPointerEnter,
      );
      window.removeEventListener('mousemove', onMouseMove);
      void telemetry.flush();
    };
  }, [enabled, sessionId, screen, trackCursorJumps]);

  return { record, recordItemTiming };
}

'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

export interface UseTimerOptions {
  durationSeconds: number;
  /**
   * Optional anchor timestamp (ISO string or anything `Date.parse` can
   * read). When provided, `secondsRemaining` is derived from
   * `durationSeconds - (now - startedAt)` on mount and after every reset,
   * so the countdown survives page reloads instead of restarting at
   * `durationSeconds`. Missing / unparseable values fall back to the
   * legacy mount-time start.
   */
  startedAt?: string | null;
  onEnd?: () => void;
  onWarning?: (secondsRemaining: number) => void;
  warningThresholds?: number[];
}

export interface UseTimerReturn {
  secondsRemaining: number;
  isRunning: boolean;
  start: () => void;
  pause: () => void;
  reset: () => void;
  formatTime: () => string;
}

const DEFAULT_WARNING_THRESHOLDS = [300, 120, 60, 30]; // 5min, 2min, 1min, 30s

function computeInitialRemaining(
  durationSeconds: number,
  startedAt: string | null | undefined,
): number {
  if (!startedAt) return durationSeconds;
  const startedMs = Date.parse(startedAt);
  if (Number.isNaN(startedMs)) return durationSeconds;
  const elapsedSeconds = Math.floor((Date.now() - startedMs) / 1000);
  const remaining = durationSeconds - elapsedSeconds;
  if (remaining <= 0) return 0;
  if (remaining > durationSeconds) return durationSeconds;
  return remaining;
}

export function useTimer({
  durationSeconds,
  startedAt,
  onEnd,
  onWarning,
  warningThresholds = DEFAULT_WARNING_THRESHOLDS,
}: UseTimerOptions): UseTimerReturn {
  const [secondsRemaining, setSecondsRemaining] = useState(() =>
    computeInitialRemaining(durationSeconds, startedAt),
  );
  const [isRunning, setIsRunning] = useState(false);
  const [hasEnded, setHasEnded] = useState(false);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const warningsGiven = useRef<Set<number>>(new Set());

  const clearTimer = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const start = useCallback(() => {
    if (isRunning) return;
    setIsRunning(true);
  }, [isRunning]);

  const pause = useCallback(() => {
    setIsRunning(false);
    clearTimer();
  }, [clearTimer]);

  const reset = useCallback(() => {
    clearTimer();
    setSecondsRemaining(computeInitialRemaining(durationSeconds, startedAt));
    setIsRunning(false);
    setHasEnded(false);
    warningsGiven.current.clear();
  }, [clearTimer, durationSeconds, startedAt]);

  const formatTime = useCallback((): string => {
    const minutes = Math.floor(secondsRemaining / 60);
    const seconds = secondsRemaining % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  }, [secondsRemaining]);

  // Single tick: when anchored to `startedAt`, the remaining time is derived
  // from wall-clock (`durationSeconds - (now - startedAt)`) rather than
  // decremented, so the countdown stays correct even when the browser
  // throttles or pauses the interval in a background tab. The interval then
  // only drives repaints; the value itself is always re-derived. Without an
  // anchor we fall back to the legacy `prev - 1` decrement.
  const tick = useCallback(() => {
    setSecondsRemaining((prev) => {
      const newValue = startedAt
        ? computeInitialRemaining(durationSeconds, startedAt)
        : prev - 1;

      // Fire warnings for every threshold crossed downward this tick. Using
      // crossing detection (rather than `=== threshold`) means thresholds the
      // timer jumped past while the tab was hidden still fire on return.
      if (onWarning) {
        for (const threshold of warningThresholds) {
          if (
            prev > threshold &&
            newValue <= threshold &&
            !warningsGiven.current.has(threshold)
          ) {
            warningsGiven.current.add(threshold);
            onWarning(threshold);
          }
        }
      }

      if (newValue <= 0) {
        clearTimer();
        setIsRunning(false);
        setHasEnded(true);
        return 0;
      }

      return newValue;
    });
  }, [startedAt, durationSeconds, onWarning, warningThresholds, clearTimer]);

  useEffect(() => {
    if (!isRunning) return;

    intervalRef.current = setInterval(tick, 1000);

    return () => clearTimer();
  }, [isRunning, clearTimer, tick]);

  // Re-sync immediately when the tab regains focus, so the correction is
  // instant instead of waiting up to ~1s for the next interval tick.
  useEffect(() => {
    if (!isRunning) return;

    const onVisibility = () => {
      if (document.visibilityState === 'visible') tick();
    };

    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('focus', tick);

    return () => {
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('focus', tick);
    };
  }, [isRunning, tick]);

  // Call onEnd outside of state updater to avoid React warning
  useEffect(() => {
    if (hasEnded) {
      onEnd?.();
    }
  }, [hasEnded, onEnd]);

  return {
    secondsRemaining,
    isRunning,
    start,
    pause,
    reset,
    formatTime,
  };
}

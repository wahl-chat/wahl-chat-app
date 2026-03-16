'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

export interface UseTimerOptions {
  durationSeconds: number;
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

export function useTimer({
  durationSeconds,
  onEnd,
  onWarning,
  warningThresholds = DEFAULT_WARNING_THRESHOLDS,
}: UseTimerOptions): UseTimerReturn {
  const [secondsRemaining, setSecondsRemaining] = useState(durationSeconds);
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
    setSecondsRemaining(durationSeconds);
    setIsRunning(false);
    setHasEnded(false);
    warningsGiven.current.clear();
  }, [clearTimer, durationSeconds]);

  const formatTime = useCallback((): string => {
    const minutes = Math.floor(secondsRemaining / 60);
    const seconds = secondsRemaining % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  }, [secondsRemaining]);

  useEffect(() => {
    if (!isRunning) return;

    intervalRef.current = setInterval(() => {
      setSecondsRemaining((prev) => {
        const newValue = prev - 1;

        // Check for warnings
        if (onWarning) {
          for (const threshold of warningThresholds) {
            if (
              newValue === threshold &&
              !warningsGiven.current.has(threshold)
            ) {
              warningsGiven.current.add(threshold);
              onWarning(threshold);
            }
          }
        }

        // Check for end
        if (newValue <= 0) {
          clearTimer();
          setIsRunning(false);
          setHasEnded(true);
          return 0;
        }

        return newValue;
      });
    }, 1000);

    return () => clearTimer();
  }, [isRunning, clearTimer, onWarning, warningThresholds]);

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

'use client';

import { cn } from '@/lib/utils';
import { useTimer } from '@/modules/exploration-study/hooks';
import { Clock } from 'lucide-react';
import { useEffect, useRef } from 'react';

export interface TaskTimerProps {
  durationSeconds: number;
  onEnd: () => void;
  className?: string;
}

export function TaskTimer({
  durationSeconds,
  onEnd,
  className,
}: TaskTimerProps) {
  const announcerRef = useRef<HTMLDivElement>(null);

  const { secondsRemaining, formatTime, start } = useTimer({
    durationSeconds,
    onEnd,
    onWarning: (seconds) => {
      // Announce time warnings to screen readers
      if (announcerRef.current) {
        const minutes = Math.floor(seconds / 60);
        const message =
          minutes > 0
            ? `Noch ${minutes} Minute${minutes > 1 ? 'n' : ''} verbleibend`
            : `Noch ${seconds} Sekunden verbleibend`;
        announcerRef.current.textContent = message;
      }
    },
  });

  // Auto-start on mount
  useEffect(() => {
    start();
  }, [start]);

  const isLowTime = secondsRemaining <= 60;
  const isCriticalTime = secondsRemaining <= 30;

  return (
    <>
      {/* Screen reader announcements */}
      <div
        ref={announcerRef}
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      />

      {/* Visual timer */}
      <div
        className={cn(
          'flex items-center gap-2 rounded-full px-3 py-1.5 transition-colors',
          isCriticalTime
            ? 'bg-destructive text-destructive-foreground'
            : isLowTime
              ? 'bg-warning text-warning-foreground'
              : 'bg-muted',
          className,
        )}
        aria-label={`Verbleibende Zeit: ${formatTime()}`}
      >
        <Clock className={cn('size-4', isCriticalTime && 'animate-pulse')} />
        <span className="font-mono text-sm font-semibold tabular-nums">
          {formatTime()}
        </span>
      </div>
    </>
  );
}

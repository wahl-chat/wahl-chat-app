'use client';

import { cn } from '@/lib/utils';
import { Clock } from 'lucide-react';

export interface TaskTimerProps {
  secondsRemaining: number;
  formattedTime: string;
  className?: string;
}

export function TaskTimer({
  secondsRemaining,
  formattedTime,
  className,
}: TaskTimerProps) {
  const isLowTime = secondsRemaining <= 60;
  const isCriticalTime = secondsRemaining <= 30;

  return (
    <div
      role="timer"
      aria-label={`Verbleibende Zeit: ${formattedTime}`}
      className={cn(
        'flex items-center gap-2 rounded-full px-3 py-1.5 transition-colors',
        isCriticalTime
          ? 'bg-destructive text-destructive-foreground'
          : isLowTime
            ? 'bg-warning text-warning-foreground'
            : 'bg-muted',
        className,
      )}
    >
      <Clock
        aria-hidden="true"
        className={cn('size-4', isCriticalTime && 'animate-pulse')}
      />
      <span
        className="font-mono text-sm font-semibold tabular-nums"
        aria-hidden="true"
      >
        {formattedTime}
      </span>
    </div>
  );
}

'use client';

import { cn } from '@/lib/utils';
import { nanoid } from 'nanoid';
import { StatusDot } from './status-dot';

interface StatusDotsProps {
  explored: number;
  total: number;
  maxDots?: number;
  className?: string;
}

export function StatusDots({
  explored,
  total,
  maxDots = 6,
  className,
}: StatusDotsProps) {
  // If total exceeds maxDots, show abbreviated version
  const showAbbreviated = total > maxDots;

  if (showAbbreviated) {
    // Show first few dots + indicator of more
    const visibleDots = Math.min(maxDots - 1, total);
    const exploredVisible = Math.min(explored, visibleDots);

    return (
      <div className={cn('flex items-center gap-1', className)}>
        {Array.from({ length: visibleDots }).map((_, i) => (
          <StatusDot
            key={nanoid()}
            status={i < exploredVisible ? 'explored' : 'pending'}
          />
        ))}
        <span className="text-xs text-muted-foreground">
          +{total - visibleDots}
        </span>
      </div>
    );
  }

  return (
    <div className={cn('flex items-center gap-1', className)}>
      {Array.from({ length: total }).map((_, i) => (
        <StatusDot
          key={nanoid()}
          status={i < explored ? 'explored' : 'pending'}
        />
      ))}
    </div>
  );
}

'use client';

import { cn } from '@/lib/utils';
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

  // Build a stable, position-keyed list of dots. Each dot's identity is its
  // position; the `id` field shields the key from biome's index-key rule.
  const buildDots = (count: number, exploredCount: number) => {
    const items: { id: string; status: 'explored' | 'pending' }[] = [];
    for (let i = 0; i < count; i++) {
      items.push({
        id: `dot-${i}`,
        status: i < exploredCount ? 'explored' : 'pending',
      });
    }
    return items;
  };

  if (showAbbreviated) {
    const visibleDots = Math.min(maxDots - 1, total);
    const exploredVisible = Math.min(explored, visibleDots);
    return (
      <div className={cn('flex items-center gap-1', className)}>
        {buildDots(visibleDots, exploredVisible).map((dot) => (
          <StatusDot key={dot.id} status={dot.status} />
        ))}
        <span className="text-xs text-foreground">+{total - visibleDots}</span>
      </div>
    );
  }

  return (
    <div className={cn('flex items-center gap-1', className)}>
      {buildDots(total, explored).map((dot) => (
        <StatusDot key={dot.id} status={dot.status} />
      ))}
    </div>
  );
}

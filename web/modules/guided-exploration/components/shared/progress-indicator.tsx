'use client';

import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import { StatusDots } from './status-dots';

type ProgressVariant = 'dots' | 'bar';

interface ProgressIndicatorProps {
  explored: number;
  total: number;
  variant?: ProgressVariant;
  showLabel?: boolean;
  className?: string;
}

export function ProgressIndicator({
  explored,
  total,
  variant = 'dots',
  showLabel = true,
  className,
}: ProgressIndicatorProps) {
  const percentage = total > 0 ? Math.round((explored / total) * 100) : 0;

  if (variant === 'bar') {
    return (
      <div className={cn('flex flex-col gap-1', className)}>
        {showLabel && (
          <span className="text-xs text-foreground">
            {explored} von {total} erkundet
          </span>
        )}
        <Progress
          value={percentage}
          aria-label={`${explored} von ${total} erkundet`}
          className="h-2"
        />
      </div>
    );
  }

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <StatusDots explored={explored} total={total} />
      {showLabel && (
        <span className="text-xs text-foreground">
          {explored}/{total}
        </span>
      )}
    </div>
  );
}

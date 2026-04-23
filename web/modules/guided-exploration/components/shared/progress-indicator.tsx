'use client';

import { Progress } from '@/components/ui/progress';
import VisuallyHidden from '@/components/visually-hidden';
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

  const srLabel = `${explored} von ${total} Themen erkundet`;

  if (variant === 'bar') {
    return (
      <div className={cn('flex flex-col gap-1', className)}>
        {showLabel && (
          <span aria-hidden="true" className="text-xs text-foreground">
            {explored} von {total} erkundet
          </span>
        )}
        <VisuallyHidden>{srLabel}</VisuallyHidden>
        <Progress value={percentage} aria-hidden="true" className="h-2" />
      </div>
    );
  }

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <StatusDots explored={explored} total={total} />
      <VisuallyHidden>{srLabel}</VisuallyHidden>
      {showLabel && (
        <span aria-hidden="true" className="text-xs text-foreground">
          {explored}/{total}
        </span>
      )}
    </div>
  );
}

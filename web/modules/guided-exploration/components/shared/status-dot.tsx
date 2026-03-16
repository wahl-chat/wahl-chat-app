'use client';

import { cn } from '@/lib/utils';

type StatusDotStatus = 'explored' | 'pending';

interface StatusDotProps {
  status: StatusDotStatus;
  className?: string;
}

export function StatusDot({ status, className }: StatusDotProps) {
  return (
    <span
      className={cn(
        'inline-block size-2 rounded-full',
        status === 'explored' ? 'bg-primary' : 'bg-muted-foreground/30',
        className,
      )}
      aria-hidden="true"
    />
  );
}

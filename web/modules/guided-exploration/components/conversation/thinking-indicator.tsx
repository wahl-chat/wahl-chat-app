'use client';

import { cn } from '@/lib/utils';
import { StarsIcon } from 'lucide-react';

interface ThinkingIndicatorProps {
  message?: string;
  className?: string;
}

/**
 * Animated thinking indicator for loading states
 * Features an AI star with a dynamic spinning ring
 */
export function ThinkingIndicator({
  message = 'Nachricht wird verarbeitet...',
  className,
}: ThinkingIndicatorProps) {
  return (
    <div
      className={cn('flex items-center gap-2 text-foreground', className)}
      role="status"
      aria-live="polite"
    >
      <div className="relative size-10">
        {/* Dynamic arc ring - rotates and changes arc length */}
        <svg
          className="absolute inset-0 size-10 animate-ai-ring-rotate"
          viewBox="0 0 50 50"
          aria-hidden="true"
        >
          {/* Background track */}
          <circle
            cx="25"
            cy="25"
            r="20"
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            strokeOpacity="0.15"
          />
          {/* Animated arc */}
          <circle
            cx="25"
            cy="25"
            r="20"
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            strokeLinecap="round"
            className="animate-ai-ring-arc"
          />
        </svg>
        {/* AI Star - gentle pulse */}
        <div className="absolute inset-0 flex items-center justify-center">
          <StarsIcon className="size-4 animate-ai-star-pulse text-current" />
        </div>
      </div>
      <span className="text-sm">{message}</span>
    </div>
  );
}

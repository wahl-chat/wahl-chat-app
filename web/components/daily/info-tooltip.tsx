'use client';

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { DAILY_THEME_CLASSES } from '@/lib/daily/fonts';
import { cn } from '@/lib/utils';
import { useState } from 'react';
import { ABOVE_CARD_LINK, FOCUS_RING } from './card-styles';

/**
 * An explanation of ``children``: on hover with a mouse, on tap on a touch
 * screen, where a tooltip would otherwise never open. Inside a card the
 * trigger sits above the card's link, and a tap does not reach a parent chip
 * or card, so it explains rather than opens the item.
 */
export function InfoTooltip({
  content,
  children,
  label,
  side = 'top',
  className,
  contentClassName = 'max-w-64',
}: {
  content: React.ReactNode;
  children: React.ReactNode;
  /** The trigger's accessible name, when its text alone does not say it. */
  label?: string;
  side?: 'top' | 'bottom';
  className?: string;
  contentClassName?: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Tooltip open={open} onOpenChange={setOpen} delayDuration={150}>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={label}
          onClick={(event) => {
            event.stopPropagation();
            setOpen(true);
          }}
          className={cn(ABOVE_CARD_LINK, FOCUS_RING, className)}
        >
          {children}
        </button>
      </TooltipTrigger>
      <TooltipContent
        side={side}
        className={cn(
          DAILY_THEME_CLASSES,
          'border-[var(--daily-border)] bg-[var(--daily-canvas)] text-[13px] leading-snug text-[var(--daily-ink)]',
          contentClassName,
        )}
      >
        {content}
      </TooltipContent>
    </Tooltip>
  );
}

import { Button, type ButtonProps } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { forwardRef } from 'react';

// The game sits in the feed's shell, so its buttons take the feed's
// .daily-theme colours instead of the app-wide button palette. Opacity
// modifiers do not work on var() colours, so hover changes opacity instead,
// and a disabled pill holds its dimmed opacity so hovering never revives it.

/** The game's call to action, so every step forward looks the same. */
const PillButton = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, ...props }, ref) => (
    <Button
      ref={ref}
      className={cn(
        'h-12 gap-2.5 self-center rounded-full bg-[var(--daily-ink)] px-6 font-display text-lg font-bold tracking-[-0.01em] text-[var(--daily-canvas)] shadow-sm ring-offset-[var(--daily-canvas)] transition-transform hover:bg-[var(--daily-ink)] hover:opacity-90 disabled:hover:opacity-50 aria-disabled:opacity-50 aria-disabled:hover:opacity-50 focus-visible:ring-[var(--daily-ink)] active:scale-[0.97] motion-reduce:active:scale-100 [&_svg]:size-5',
        className,
      )}
      {...props}
    />
  ),
);
PillButton.displayName = 'PillButton';

/** For `variant="outline"`: the answer buttons and other secondary steps. */
export const OUTLINE_BUTTON =
  'border-[var(--daily-border)] bg-[var(--daily-canvas)] ring-offset-[var(--daily-canvas)] hover:bg-[var(--daily-surface)] hover:text-[var(--daily-ink)] focus-visible:ring-[var(--daily-ink)]';

/** For `variant="ghost"`: a quiet text step such as "Zurück zu heute". */
export const GHOST_BUTTON =
  'ring-offset-[var(--daily-canvas)] hover:bg-[var(--daily-surface)] hover:text-[var(--daily-ink)] focus-visible:ring-[var(--daily-ink)]';

export default PillButton;

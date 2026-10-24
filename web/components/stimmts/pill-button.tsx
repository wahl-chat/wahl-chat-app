import { Button, type ButtonProps } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { forwardRef } from 'react';

/**
 * The game's call to action between screens ("Ergebnis teilen", "Zum
 * Ergebnis"): a pill sized to its label, in the display face, like "Los
 * geht's" at the start, so every step forward looks the same.
 */
const PillButton = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, ...props }, ref) => (
    <Button
      ref={ref}
      className={cn(
        'h-12 gap-2.5 self-center rounded-full px-6 font-display text-lg font-bold tracking-[-0.01em] shadow-sm transition-transform active:scale-[0.97] motion-reduce:active:scale-100 [&_svg]:size-5',
        className,
      )}
      {...props}
    />
  ),
);
PillButton.displayName = 'PillButton';

export default PillButton;

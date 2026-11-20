'use client';

import { styleButtonLabel } from '@/lib/stimmts/style-sheet-view';
import { useStimmtsStyle } from '@/lib/stimmts/style-store';
import { cn } from '@/lib/utils';
import { Palette } from 'lucide-react';
import { useState } from 'react';
import PillButton from './pill-button';
import StyleSheet from './style-sheet';

/**
 * Opens the style sheet from the result screen. The red dot stays until the
 * sheet has been opened once after a style unlocked.
 */
function StyleButton({ className }: { className?: string }) {
  const { fresh } = useStimmtsStyle();
  const [open, setOpen] = useState(false);
  const hasFresh = fresh.length > 0;

  return (
    <>
      <PillButton
        type="button"
        variant="outline"
        aria-label={styleButtonLabel(hasFresh)}
        onClick={() => setOpen(true)}
        className={cn(
          "relative h-10 gap-2 self-start border border-[var(--daily-border)] bg-[var(--daily-surface)] px-4 text-base text-[var(--daily-ink)] after:absolute after:-inset-y-0.5 after:inset-x-0 after:content-[''] hover:bg-[var(--daily-surface)] [&_svg]:size-4",
          className,
        )}
      >
        <Palette aria-hidden strokeWidth={2.25} />
        Stil ändern
        {hasFresh && (
          <span
            aria-hidden
            className="absolute -right-1 -top-1 size-[9px] rounded-full bg-brand-red"
          />
        )}
      </PillButton>
      <StyleSheet open={open} onOpenChange={setOpen} />
    </>
  );
}

export default StyleButton;

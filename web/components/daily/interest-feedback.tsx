'use client';

import { useAnonymousAuth } from '@/components/anonymous-auth';
import { readInterest, recordInterest } from '@/lib/daily/interest';
import type { FeedInterest } from '@/lib/firebase/firebase';
import { cn } from '@/lib/utils';
import { useEffect, useState } from 'react';
import { FOCUS_RING, MUTED_TEXT, PILL_ACTIVE } from './card-styles';

const OPTIONS: { value: FeedInterest; label: string }[] = [
  { value: 'yes', label: 'Ja' },
  { value: 'no', label: 'Nein' },
];

function InterestFeedback({
  itemKey,
  grouped = false,
  className,
}: {
  itemKey: string;
  /** Keep the label beside the buttons instead of across the row from them,
   * for footers that share the row with "Mehr erfahren". */
  grouped?: boolean;
  className?: string;
}) {
  const { user } = useAnonymousAuth();
  const [answer, setAnswer] = useState<FeedInterest | null>(null);

  // localStorage only exists after hydration.
  useEffect(() => setAnswer(readInterest()[itemKey] ?? null), [itemKey]);

  const choose = (value: FeedInterest) => {
    setAnswer(value);
    void recordInterest(user?.uid, itemKey, value);
  };

  return (
    <fieldset
      className={cn(
        // relative: the sr-only legend is absolutely positioned and must not
        // escape a sideways scroller, or it widens the page on touch devices.
        'relative flex min-w-0 items-center gap-1.5',
        grouped && 'justify-end',
        className,
      )}
    >
      <legend className="sr-only">Interessant?</legend>
      <span
        aria-hidden
        className={cn(
          'whitespace-nowrap text-sm',
          grouped ? 'mr-1' : 'mr-auto',
          MUTED_TEXT,
        )}
      >
        Interessant?
      </span>
      {OPTIONS.map(({ value, label }) => (
        <button
          key={value}
          type="button"
          aria-pressed={answer === value}
          onClick={() => choose(value)}
          className={cn(
            FOCUS_RING,
            'h-10 min-w-11 shrink-0 rounded-lg bg-[var(--daily-surface)] px-3 text-[15px] transition-colors hover:bg-[var(--daily-border)]',
            answer === value && PILL_ACTIVE,
          )}
        >
          {label}
        </button>
      ))}
    </fieldset>
  );
}

export default InterestFeedback;

'use client';

import { useAnonymousAuth } from '@/components/anonymous-auth';
import { readInterest, recordInterest } from '@/lib/daily/interest';
import type { FeedInterest } from '@/lib/firebase/firebase';
import { cn } from '@/lib/utils';
import { type LucideIcon, ThumbsDownIcon, ThumbsUpIcon } from 'lucide-react';
import { Fragment, useEffect, useState } from 'react';
import { FOCUS_RING, MUTED_TEXT } from './card-styles';

const OPTIONS: { value: FeedInterest; label: string; Icon: LucideIcon }[] = [
  { value: 'yes', label: 'Interessant', Icon: ThumbsUpIcon },
  { value: 'no', label: 'Nicht interessant', Icon: ThumbsDownIcon },
];

/** "Interessant?" over 👍 | 👎, bottom left of every card. */
function InterestFeedback({
  itemKey,
  legacyKeys = [],
  className,
}: {
  itemKey: string;
  /** Older keys of the same item, so an answer given under one still shows. */
  legacyKeys?: string[];
  className?: string;
}) {
  const { user } = useAnonymousAuth();
  const [answer, setAnswer] = useState<FeedInterest | null>(null);

  // localStorage only exists after hydration.
  const legacy = legacyKeys.join(',');
  useEffect(() => {
    const stored = readInterest();
    const key = [itemKey, ...legacy.split(',')].find((k) => k && stored[k]);
    setAnswer(key ? stored[key] : null);
  }, [itemKey, legacy]);

  const choose = (value: FeedInterest) => {
    setAnswer(value);
    void recordInterest(user?.uid, itemKey, value);
  };

  return (
    <fieldset
      className={cn(
        // relative: the sr-only legend is absolutely positioned and must not
        // escape a sideways scroller, or it widens the page on touch devices.
        'relative flex min-w-0 flex-col',
        className,
      )}
    >
      <legend className="sr-only">Interessant?</legend>
      <span aria-hidden className={cn('text-[13px]', MUTED_TEXT)}>
        Interessant?
      </span>
      {/* Pulled left so the first icon lines up with the label above. */}
      <div className="-ml-2.5 flex items-center">
        {OPTIONS.map(({ value, label, Icon }, i) => {
          const pressed = answer === value;
          return (
            <Fragment key={value}>
              {i > 0 && (
                <span
                  aria-hidden
                  className="h-[18px] w-px bg-[var(--daily-border)]"
                />
              )}
              <button
                type="button"
                aria-label={label}
                aria-pressed={pressed}
                onClick={() => choose(value)}
                className={cn(
                  FOCUS_RING,
                  'flex size-10 items-center justify-center rounded-lg transition-colors hover:bg-[var(--daily-surface)]',
                  pressed ? 'text-[var(--daily-ink)]' : MUTED_TEXT,
                )}
              >
                <Icon
                  className="size-[18px]"
                  strokeWidth={pressed ? 2.2 : 2}
                  fill={pressed ? 'currentColor' : 'none'}
                  fillOpacity={pressed ? 0.12 : undefined}
                  aria-hidden
                />
              </button>
            </Fragment>
          );
        })}
      </div>
    </fieldset>
  );
}

export default InterestFeedback;

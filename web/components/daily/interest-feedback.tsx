'use client';

import { useAnonymousAuth } from '@/components/anonymous-auth';
import { readInterest, recordInterest } from '@/lib/daily/interest';
import type { FeedInterest } from '@/lib/firebase/firebase';
import { cn } from '@/lib/utils';
import { type LucideIcon, ThumbsDownIcon, ThumbsUpIcon } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { Fragment, useEffect, useState } from 'react';
import { FOCUS_RING, MUTED_TEXT } from './card-styles';
import { InfoTooltip } from './info-tooltip';

const OPTIONS: {
  value: FeedInterest;
  label: 'interestYes' | 'interestNo';
  Icon: LucideIcon;
}[] = [
  { value: 'yes', label: 'interestYes', Icon: ThumbsUpIcon },
  { value: 'no', label: 'interestNo', Icon: ThumbsDownIcon },
];

/** Why we ask: on hover with a mouse, on tap on a touch screen. */
function InterestQuestion() {
  const t = useTranslations('feed');
  return (
    <InfoTooltip
      content={t('interestWhy')}
      className={cn(
        'self-start rounded text-left text-[13px] underline decoration-dotted underline-offset-2',
        MUTED_TEXT,
      )}
    >
      {t('interesting')}
    </InfoTooltip>
  );
}

/** "Interessant für dich?" over 👍 | 👎, bottom left of every card. */
function InterestFeedback({
  itemKey,
  className,
}: {
  itemKey: string;
  className?: string;
}) {
  const t = useTranslations('feed');
  const { user } = useAnonymousAuth();
  const [answer, setAnswer] = useState<FeedInterest | null>(null);

  // localStorage only exists after hydration.
  useEffect(() => {
    setAnswer(readInterest()[itemKey] ?? null);
  }, [itemKey]);

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
      <legend className="sr-only">{t('interesting')}</legend>
      <InterestQuestion />
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
                aria-label={t(label)}
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

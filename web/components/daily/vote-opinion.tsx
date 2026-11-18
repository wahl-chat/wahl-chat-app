'use client';

import type { VoteOpinion as VoteChoice } from '@/lib/daily/opinions';
import { SEAT_FILLS } from '@/lib/daily/palette';
import type { FeedOpinions } from '@/lib/daily/use-feed-opinions';
import { cn } from '@/lib/utils';
import { CheckIcon, XIcon } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useId } from 'react';
import { FOCUS_RING, MUTED_TEXT, SECTION_LABEL } from './card-styles';
import { CommunityHemicycle } from './hemicycle';

const CHOICES: {
  value: VoteChoice;
  label: 'accept' | 'reject';
  color: string;
  Icon: typeof CheckIcon;
}[] = [
  {
    value: 'accept',
    label: 'accept',
    color: SEAT_FILLS.yes,
    Icon: CheckIcon,
  },
  { value: 'reject', label: 'reject', color: SEAT_FILLS.no, Icon: XIcon },
];

/**
 * "Wie hättest du abgestimmt?": two large buttons until the reader has
 * answered, then their answer beside everyone's. The totals stay hidden until
 * then, so they cannot sway the answer. Tapping the chosen answer again takes
 * it back.
 */
export function VoteOpinion({ opinions }: { opinions: FeedOpinions }) {
  const t = useTranslations('opinions.vote');
  const headingId = useId();
  const choice = opinions.opinion.vote;
  const counts = opinions.counts;
  const choose = (value: VoteChoice) =>
    opinions.choose({ kind: 'vote' }, choice === value ? null : value);

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-2.5">
      <h3 id={headingId} className={SECTION_LABEL}>
        {t('question')}
      </h3>
      {choice === null ? (
        <div className="flex gap-2">
          {CHOICES.map(({ value, label, color, Icon }) => (
            <button
              key={value}
              type="button"
              aria-pressed={false}
              onClick={() => choose(value)}
              className={cn(
                FOCUS_RING,
                'inline-flex min-h-[46px] flex-1 items-center justify-center gap-1.5 rounded-[10px] text-[15px] font-bold text-white transition-opacity hover:opacity-90',
              )}
              style={{ backgroundColor: color }}
            >
              <Icon className="size-4" strokeWidth={3} aria-hidden />
              {t(label)}
            </button>
          ))}
        </div>
      ) : (
        <div className="flex items-center gap-4">
          <div className="flex flex-col gap-1.5">
            {CHOICES.map(({ value, label, color, Icon }) => {
              const chosen = choice === value;
              return (
                <button
                  key={value}
                  type="button"
                  aria-label={t(label)}
                  aria-pressed={chosen}
                  onClick={() => choose(value)}
                  className={cn(
                    FOCUS_RING,
                    'flex h-11 w-12 items-center justify-center rounded-[10px] border transition-colors',
                    !chosen &&
                      'border-[var(--daily-border)] bg-[var(--daily-canvas)] text-[var(--daily-muted)] hover:bg-[var(--daily-surface)]',
                  )}
                  style={
                    chosen
                      ? {
                          backgroundColor: color,
                          borderColor: color,
                          color: '#FFFFFF',
                        }
                      : undefined
                  }
                >
                  <Icon className="size-4" strokeWidth={3} aria-hidden />
                </button>
              );
            })}
          </div>
          {counts?.vote && (
            <div className="flex flex-1 flex-col items-center gap-0.5">
              <CommunityHemicycle
                accept={counts.vote.accept}
                reject={counts.vote.reject}
                className="max-w-[200px]"
              />
              <p
                aria-hidden
                className="text-[18px] font-extrabold tabular-nums tracking-tight"
              >
                {counts.vote.accept} : {counts.vote.reject}
              </p>
            </div>
          )}
          {counts && !counts.vote && (
            <p className={cn('flex-1 text-center text-[13px]', MUTED_TEXT)}>
              {t('tooFew')}
            </p>
          )}
        </div>
      )}
    </section>
  );
}

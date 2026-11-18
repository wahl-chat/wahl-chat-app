'use client';

import type { DetailItem } from '@/lib/daily/items';
import { shareItem } from '@/lib/daily/share';
import type { TermRef } from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { ArrowRightIcon, Share2Icon } from 'lucide-react';
import { useTranslations } from 'next-intl';
import {
  ABOVE_CARD_LINK,
  CARD_ACTION,
  FOCUS_RING,
  MUTED_TEXT,
} from './card-styles';
import { GlossaryText } from './glossary-text';
import InterestFeedback from './interest-feedback';

/** Teaser text, cut after two lines, and the way into the detail. */
export function ItemTeaser({
  text,
  terms,
  label,
  onOpen,
}: {
  text: string | null;
  /** The expert terms in it the glossary explains. */
  terms?: TermRef[];
  /** The item's title, so the link names what it opens. */
  label: string;
  onOpen: () => void;
}) {
  const t = useTranslations('feed');
  return (
    <div className="flex flex-col items-start gap-3">
      {text && (
        <p className="line-clamp-2 text-[15px] leading-normal text-[var(--daily-body)]">
          <GlossaryText text={text} terms={terms} />
        </p>
      )}
      <button
        type="button"
        onClick={onOpen}
        aria-label={t('moreAbout', { title: label })}
        className={cn(FOCUS_RING, ABOVE_CARD_LINK, CARD_ACTION)}
      >
        {t('more')}
        <ArrowRightIcon className="size-4" aria-hidden />
      </button>
    </div>
  );
}

/** "Interessant für dich?" bottom left, share bottom right. */
export function CardFooter({ item }: { item: DetailItem }) {
  const t = useTranslations('feed');
  return (
    <div className="mt-auto flex items-end justify-between gap-3">
      <InterestFeedback itemKey={item.key} className={ABOVE_CARD_LINK} />
      <button
        type="button"
        aria-label={t('share')}
        onClick={() => shareItem(item, t('linkCopied'))}
        className={cn(
          FOCUS_RING,
          ABOVE_CARD_LINK,
          'flex size-10 shrink-0 items-center justify-center rounded-full transition-colors hover:bg-[var(--daily-surface)] hover:text-[var(--daily-ink)]',
          MUTED_TEXT,
        )}
      >
        <Share2Icon className="size-5" aria-hidden />
      </button>
    </div>
  );
}

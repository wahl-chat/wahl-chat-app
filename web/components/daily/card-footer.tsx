'use client';

import { type DetailItem, legacyKeys } from '@/lib/daily/items';
import { shareItem } from '@/lib/daily/share';
import { cn } from '@/lib/utils';
import { Share2Icon } from 'lucide-react';
import { FOCUS_RING, MUTED_TEXT } from './card-styles';
import { useFeedLocale } from './feed-locale';
import InterestFeedback from './interest-feedback';

/** Teaser text, cut after two lines, and the way into the detail. */
export function ItemTeaser({
  text,
  label,
  onOpen,
}: {
  text: string | null;
  /** The item's title, so the link names what it opens. */
  label: string;
  onOpen: () => void;
}) {
  const { t } = useFeedLocale();
  return (
    <div>
      {text && (
        <p className="line-clamp-2 text-[15px] leading-normal text-[var(--daily-body)]">
          {text}
        </p>
      )}
      <button
        type="button"
        onClick={onOpen}
        aria-label={t.moreAbout(label)}
        className={cn(
          FOCUS_RING,
          'flex min-h-8 items-center rounded-md text-[15px] hover:text-[var(--daily-ink)]',
          MUTED_TEXT,
        )}
      >
        {t.more}
      </button>
    </div>
  );
}

/** "Interessant?" bottom left, share bottom right. */
export function CardFooter({ item }: { item: DetailItem }) {
  const { t } = useFeedLocale();
  return (
    <div className="mt-auto flex items-end justify-between gap-3">
      <InterestFeedback itemKey={item.key} legacyKeys={legacyKeys(item)} />
      <button
        type="button"
        aria-label={t.share}
        onClick={() => shareItem(item, t.linkCopied)}
        className={cn(
          FOCUS_RING,
          'flex size-10 shrink-0 items-center justify-center rounded-full transition-colors hover:bg-[var(--daily-surface)] hover:text-[var(--daily-ink)]',
          MUTED_TEXT,
        )}
      >
        <Share2Icon className="size-5" aria-hidden />
      </button>
    </div>
  );
}

'use client';

import { feedPicks } from '@/lib/chat-feed';
import { getFeedItem } from '@/lib/firebase/firebase';
import type { FeedItem } from '@/lib/firebase/firebase.types';
import { useEffect, useState } from 'react';
import FeedPickThumb from './feed-pick-thumb';
import { useLeaveForFeed } from './use-leave-for-feed';

const shortDay = new Intl.DateTimeFormat('de-DE', {
  day: 'numeric',
  month: 'short',
  timeZone: 'UTC',
});

/** Feed items matching a question, as a row under its answer. The answer
 * does not draw on them; they are a way into the feed. */
function RelatedFeedItems({ ids }: { ids?: string[] }) {
  const [items, setItems] = useState<FeedItem[]>([]);
  const leave = useLeaveForFeed();
  const key = ids?.join(',') ?? '';

  useEffect(() => {
    if (!key) return;
    let cancelled = false;
    Promise.all(
      key.split(',').map((id) => getFeedItem(id).catch(() => null)),
    ).then((found) => {
      if (!cancelled) {
        setItems(
          found.filter(
            (item): item is FeedItem => item?.status === 'published',
          ),
        );
      }
    });
    return () => {
      cancelled = true;
    };
  }, [key]);

  if (items.length === 0) return null;

  return (
    <section
      aria-label="Passt dazu im Bundestag"
      className="flex flex-col gap-2"
    >
      <h3 className="text-sm font-semibold text-muted-foreground">
        Passt dazu im Bundestag
      </h3>
      <ul className="-mx-3 flex snap-x gap-3 overflow-x-auto px-3 pb-1 md:mx-0 md:px-0">
        {items.map((item) => {
          // Relevance order, as the backend ranked them.
          const pick = feedPicks([item])[0];
          if (!pick) return null;
          return (
            <li key={pick.id} className="w-56 shrink-0 snap-start">
              <button
                type="button"
                onClick={() => leave.openItem(item)}
                className="flex size-full flex-col overflow-hidden rounded-xl border bg-background text-left transition-colors hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <FeedPickThumb pick={pick} className="w-full rounded-none" />
                <span className="flex flex-col gap-0.5 p-2.5">
                  <span className="text-xs text-muted-foreground">
                    {pick.kind === 'vote' ? 'Abstimmung' : 'Debatte'} ·{' '}
                    {shortDay.format(new Date(`${pick.date}T00:00:00Z`))}
                  </span>
                  <span className="line-clamp-3 text-sm font-semibold leading-snug">
                    {pick.headline}
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export default RelatedFeedItems;

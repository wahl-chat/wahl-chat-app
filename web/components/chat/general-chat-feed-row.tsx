'use client';

import { useChatStore } from '@/components/providers/chat-store-provider';
import type { FeedPick } from '@/lib/chat-feed';
import { cn } from '@/lib/utils';
import { ChevronRightIcon } from 'lucide-react';
import { useState } from 'react';
import ChatFeedPicker, { pickMeta } from './chat-feed-picker';
import FeedPickThumb from './feed-pick-thumb';

const SHOWN = 6;

type Props = {
  picks: FeedPick[];
};

/** The newest feed items as cards, so a chat about one is one tap away;
 * the rest sit behind "Alle". */
function GeneralChatFeedRow({ picks }: Props) {
  const anchor = useChatStore((state) => state.anchor);
  const setAnchor = useChatStore((state) => state.setAnchor);
  const anchorItemId =
    anchor && 'feed_item_id' in anchor ? anchor.feed_item_id : undefined;
  const [pickerOpen, setPickerOpen] = useState(false);

  if (picks.length === 0) return null;

  return (
    <section className="flex w-full max-w-2xl flex-col gap-2">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold">Über ein Thema aus dem Feed</h2>
        <button
          type="button"
          onClick={() => setPickerOpen(true)}
          className="flex items-center text-sm font-medium text-muted-foreground underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          Alle
          <ChevronRightIcon className="size-4" />
        </button>
      </div>
      <ul className="-mx-3 flex snap-x snap-mandatory scroll-px-3 gap-2 overflow-x-auto px-3 pb-1 [scrollbar-width:none] md:mx-0 md:px-0">
        {picks.slice(0, SHOWN).map((pick) => {
          const current = pick.id === anchorItemId;
          return (
            <li key={pick.id} className="w-40 shrink-0 snap-start md:w-44">
              <button
                type="button"
                onClick={() => setAnchor({ feed_item_id: pick.id })}
                aria-pressed={current}
                className={cn(
                  'flex size-full flex-col gap-1.5 rounded-lg border p-1.5 text-left transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  current && 'border-foreground bg-muted',
                )}
              >
                <FeedPickThumb pick={pick} className="w-full" />
                <span className="px-0.5 text-xs text-muted-foreground">
                  {pickMeta(pick)}
                </span>
                <span className="line-clamp-3 px-0.5 text-sm leading-snug">
                  {pick.headline}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      <ChatFeedPicker open={pickerOpen} onOpenChange={setPickerOpen} />
    </section>
  );
}

export default GeneralChatFeedRow;

'use client';

import LoadingSpinner from '@/components/loading-spinner';
import { useChatStore } from '@/components/providers/chat-store-provider';
import { Input } from '@/components/ui/input';
import { type FeedPick, filterPicks, pickMeta } from '@/lib/chat-feed';
import { getChatFeedPicks } from '@/lib/server-actions/chat-feed-picks';
import { cn } from '@/lib/utils';
import { useEffect, useMemo, useState } from 'react';
import FeedPickThumb from './feed-pick-thumb';
import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
} from './responsive-drawer-dialog';

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

/** Picks the feed item the general chat is about; replaces its anchor. */
function ChatFeedPicker({ open, onOpenChange }: Props) {
  return (
    <ResponsiveDialog open={open} onOpenChange={onOpenChange}>
      <ResponsiveDialogContent className="md:max-w-lg">
        <ResponsiveDialogHeader className="text-left">
          <ResponsiveDialogTitle>Aus dem Feed</ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            Wähle eine Debatte oder Abstimmung der letzten zwei Wochen als Thema
            des Chats.
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>
        {open && <FeedPickList onPicked={() => onOpenChange(false)} />}
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}

function FeedPickList({ onPicked }: { onPicked: () => void }) {
  const anchor = useChatStore((state) => state.anchor);
  const setAnchor = useChatStore((state) => state.setAnchor);
  const anchorItemId =
    anchor && 'feed_item_id' in anchor ? anchor.feed_item_id : undefined;
  const [picks, setPicks] = useState<FeedPick[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [query, setQuery] = useState('');

  useEffect(() => {
    let cancelled = false;
    getChatFeedPicks()
      .then((result) => {
        if (!cancelled) setPicks(result);
      })
      .catch((error) => {
        console.error('Failed to load the feed for the chat', error);
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const shown = useMemo(
    () => (picks ? filterPicks(picks, query) : []),
    [picks, query],
  );

  function handlePick(pick: FeedPick) {
    if (pick.id !== anchorItemId) {
      setAnchor({ feed_item_id: pick.id });
    }
    onPicked();
  }

  return (
    <div className="flex min-h-0 flex-col gap-2 px-4 pb-4 md:px-0 md:pb-0">
      <Input
        type="search"
        placeholder="Nach Thema suchen…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        aria-label="Feed durchsuchen"
      />
      <div className="max-h-[55vh] overflow-y-auto overscroll-contain md:max-h-[60vh]">
        {failed ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            Der Feed konnte nicht geladen werden.
          </p>
        ) : !picks ? (
          <div className="flex justify-center py-6">
            <LoadingSpinner />
          </div>
        ) : shown.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            {picks.length === 0
              ? 'Im Feed ist gerade nichts.'
              : 'Nichts gefunden.'}
          </p>
        ) : (
          <ul className="flex flex-col gap-1">
            {shown.map((pick) => {
              const current = pick.id === anchorItemId;
              return (
                <li key={pick.id}>
                  <button
                    type="button"
                    onClick={() => handlePick(pick)}
                    aria-current={current || undefined}
                    className={cn(
                      'flex w-full items-center gap-3 rounded-md p-1.5 text-left transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                      current && 'bg-muted',
                    )}
                  >
                    <FeedPickThumb pick={pick} className="w-24" />
                    <span className="flex min-w-0 flex-col">
                      <span className="text-xs text-muted-foreground">
                        {pickMeta(pick)}
                      </span>
                      <span className="line-clamp-2 text-sm">
                        {pick.headline}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

export default ChatFeedPicker;

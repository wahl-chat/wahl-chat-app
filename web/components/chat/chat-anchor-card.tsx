'use client';

import { useChatStore } from '@/components/providers/chat-store-provider';
import { FEED_ITEM_ID, anchorCard } from '@/lib/chat-anchor';
import { getFeedItem, getProcedure } from '@/lib/firebase/firebase';
import type { FeedItem, StoredProcedure } from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import {
  ChevronLeftIcon,
  LandmarkIcon,
  ListChecksIcon,
  VoteIcon,
} from 'lucide-react';
import Link from 'next/link';
import { useEffect, useState } from 'react';

/** The feed item, vote or procedure a general chat is about, pinned above
 * the conversation, with the way back to the feed. */
function ChatAnchorCard() {
  const anchor = useChatStore((state) => state.anchor);
  const feedItemId =
    anchor && 'feed_item_id' in anchor ? anchor.feed_item_id : null;
  const vorgangId = anchor && 'vorgang_id' in anchor ? anchor.vorgang_id : null;
  const [loaded, setLoaded] = useState<{
    id: string;
    item: FeedItem | null;
  } | null>(null);
  const [procedure, setProcedure] = useState<StoredProcedure | null>(null);
  // The feed item a procedure chat was opened from, for the way back.
  const [from, setFrom] = useState<FeedItem | null>(null);

  useEffect(() => {
    if (!vorgangId) {
      return;
    }
    const fromId = new URLSearchParams(window.location.search).get('from');
    if (!fromId || !FEED_ITEM_ID.test(fromId)) {
      return;
    }
    let cancelled = false;
    getFeedItem(fromId)
      .catch(() => null)
      .then((found) => {
        if (!cancelled) {
          setFrom(found);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [vorgangId]);

  useEffect(() => {
    if (!vorgangId) {
      return;
    }
    let cancelled = false;
    getProcedure(vorgangId)
      .catch((error) => {
        console.error('Failed to load the anchored procedure', error);
        return null;
      })
      .then((found) => {
        if (!cancelled) {
          setProcedure(found);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [vorgangId]);

  useEffect(() => {
    if (!feedItemId) {
      return;
    }
    let cancelled = false;
    getFeedItem(feedItemId)
      .catch((error) => {
        console.error('Failed to load the anchored feed item', error);
        return null;
      })
      .then((item) => {
        if (!cancelled) {
          setLoaded({ id: feedItemId, item });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [feedItemId]);

  if (!anchor) {
    return null;
  }
  const item = loaded?.id === feedItemId ? loaded.item : null;
  const card = anchorCard(
    anchor,
    item,
    procedure?.vorgang_id === vorgangId ? procedure : null,
    from,
  );
  if (!card) {
    return null;
  }
  const Icon =
    card.kind === 'Abstimmung'
      ? VoteIcon
      : card.kind === 'Verfahren'
        ? ListChecksIcon
        : LandmarkIcon;
  const meta = [card.kind, card.date, card.outcome].filter(Boolean).join(' · ');

  const back = (label: string, className: string) =>
    card.feedHref && (
      <Link
        href={card.feedHref}
        aria-label="Zurück zum Feed"
        className={cn(
          'flex shrink-0 items-center gap-0.5 rounded-md font-medium underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          className,
        )}
      >
        <ChevronLeftIcon className="size-4" />
        {label}
      </Link>
    );

  return (
    <div className="mx-3 mt-3 flex items-center gap-3 rounded-lg border bg-muted/50 px-3 py-2 md:mx-[35px] md:py-2.5">
      <span className="hidden size-9 shrink-0 items-center justify-center rounded-md bg-muted md:flex">
        <Icon className="size-4" />
      </span>
      <div className="flex min-w-0 grow flex-col">
        <div className="flex items-center justify-between gap-2">
          <span className="flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground">
            <Icon className="size-3.5 shrink-0 md:hidden" />
            <span className="truncate">{meta}</span>
          </span>
          {back('Feed', '-my-1 -mr-1.5 min-h-6 px-1.5 py-1 text-xs md:hidden')}
        </div>
        <span className="line-clamp-2 text-sm font-semibold">{card.title}</span>
      </div>
      {back('Zurück zum Feed', 'hidden text-sm md:flex')}
    </div>
  );
}

export default ChatAnchorCard;

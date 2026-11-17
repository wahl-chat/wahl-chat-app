'use client';

import { useChatStore } from '@/components/providers/chat-store-provider';
import { anchorCard } from '@/lib/chat-anchor';
import { getFeedItem, getProcedure } from '@/lib/firebase/firebase';
import type { FeedItem, StoredProcedure } from '@/lib/firebase/firebase.types';
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

  return (
    <div className="mx-3 mt-3 flex items-center gap-3 rounded-lg border bg-muted/50 px-3 py-2.5 md:mx-[35px]">
      <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-muted">
        <Icon className="size-4" />
      </span>
      <div className="flex min-w-0 grow flex-col">
        <span className="text-xs text-muted-foreground">{meta}</span>
        <span className="line-clamp-2 text-sm font-semibold">{card.title}</span>
      </div>
      {card.feedHref && (
        <Link
          href={card.feedHref}
          className="flex shrink-0 items-center gap-0.5 rounded-md text-sm font-medium underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ChevronLeftIcon className="size-4" />
          Zurück zum Feed
        </Link>
      )}
    </div>
  );
}

export default ChatAnchorCard;

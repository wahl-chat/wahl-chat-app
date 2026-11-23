'use client';

import { ProcedureTimeline } from '@/components/daily/procedure-section';
import { useChatStore } from '@/components/providers/chat-store-provider';
import { FEED_ITEM_ID, anchorCard } from '@/lib/chat-anchor';
import { feedPicks } from '@/lib/chat-feed';
import { clearReturnChat, takeFromFeed } from '@/lib/daily/chat-handoff';
import { DAILY_THEME_CLASSES } from '@/lib/daily/fonts';
import { procedureTimeline } from '@/lib/daily/procedures';
import {
  getFeedItem,
  getFeedItemsForProcedure,
  getProcedure,
} from '@/lib/firebase/firebase';
import type {
  FeedItem,
  ProcedureSummary,
  StoredProcedure,
} from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import {
  ChevronDownIcon,
  ChevronLeftIcon,
  LandmarkIcon,
  ListChecksIcon,
  VoteIcon,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useId, useRef, useState } from 'react';
import { useChatHost } from './chat-host';
import FeedPickThumb from './feed-pick-thumb';

/** A procedure as feed items carry it, with its steps; null until loaded
 * or when no item does. */
function useProcedureSummary(vorgangId: string | null) {
  const [loaded, setLoaded] = useState<{
    id: string;
    procedure: ProcedureSummary | null;
  } | null>(null);
  useEffect(() => {
    if (!vorgangId) return;
    let cancelled = false;
    getFeedItemsForProcedure(vorgangId)
      .catch(() => [])
      .then((items) => {
        const procedure =
          items
            .flatMap((found) => found.procedures ?? [])
            .find((candidate) => candidate.vorgang_id === vorgangId) ?? null;
        if (!cancelled) setLoaded({ id: vorgangId, procedure });
      });
    return () => {
      cancelled = true;
    };
  }, [vorgangId]);
  return loaded?.id === vorgangId ? loaded.procedure : null;
}

/** The feed item, vote or procedure a general chat is about, pinned above
 * the conversation: its details one tap away, and on the chat page the way
 * back to the feed. */
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
  const host = useChatHost();
  const router = useRouter();
  const [expanded, setExpanded] = useState(false);
  const summary = useProcedureSummary(vorgangId);
  const hasTimeline = summary ? procedureTimeline(summary) !== null : false;
  const detailsId = useId();
  const fromFeed = useRef(false);
  const marksRead = useRef(false);
  useEffect(() => {
    // Once: the marks are consumed on read, and StrictMode runs this twice.
    if (host.mode !== 'page' || marksRead.current) return;
    marksRead.current = true;
    fromFeed.current = takeFromFeed();
    // Inside a chat, the feed's way back to it is stale.
    clearReturnChat();
  }, [host.mode]);

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
  const pick = item ? feedPicks([item])[0] : undefined;
  const teaser = item?.content.de.teaser;

  const back = (label: string, className: string) =>
    host.mode === 'page' &&
    card.feedHref && (
      <Link
        href={card.feedHref}
        onClick={(event) => {
          // Back in history keeps the feed where the reader left it.
          if (fromFeed.current) {
            event.preventDefault();
            router.back();
          }
        }}
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
    <div className="mx-3 mt-3 flex flex-col gap-1.5 md:mx-[35px]">
      {back('Zurück zum Feed', '-ml-1 self-start px-1 py-1 text-sm')}
      <div className="flex flex-col rounded-xl border bg-muted/40">
        <div className="flex items-center gap-3 p-2 pr-3">
          {pick ? (
            <FeedPickThumb pick={pick} className="w-20 md:w-24" />
          ) : (
            <span className="flex size-11 shrink-0 items-center justify-center rounded-md bg-muted">
              <Icon className="size-4" />
            </span>
          )}
          <div className="flex min-w-0 grow flex-col gap-0.5">
            <span
              className={cn(
                'text-xs text-muted-foreground',
                !expanded && 'truncate',
              )}
            >
              {meta}
            </span>
            <span
              className={cn(
                'text-sm font-semibold leading-snug',
                !expanded && 'line-clamp-2',
              )}
            >
              {card.title}
            </span>
            {teaser && !expanded && (
              <span className="hidden text-xs text-muted-foreground md:line-clamp-1">
                {teaser}
              </span>
            )}
          </div>
          {(item || hasTimeline) && (
            <button
              type="button"
              onClick={() => setExpanded((open) => !open)}
              aria-expanded={expanded}
              aria-controls={detailsId}
              className="flex min-h-11 shrink-0 items-center gap-0.5 rounded-md px-2 text-sm font-semibold hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              Details
              <ChevronDownIcon
                className={cn(
                  'size-4 transition-transform',
                  expanded && 'rotate-180',
                )}
                aria-hidden
              />
            </button>
          )}
        </div>
        {!item && summary && expanded && hasTimeline && (
          <div
            id={detailsId}
            className={cn(
              DAILY_THEME_CLASSES,
              'border-t !bg-transparent px-2 py-2',
            )}
          >
            <ProcedureTimeline procedure={summary} />
          </div>
        )}
        {item && expanded && (
          <div
            id={detailsId}
            className="flex flex-col gap-2 border-t px-3 pb-3 pt-2.5 text-sm leading-relaxed"
          >
            {teaser && <p>{teaser}</p>}
            {item.content.de.key_points.length > 0 && (
              <ul className="ml-4 list-disc space-y-1 text-muted-foreground">
                {item.content.de.key_points.map((point) => (
                  <li key={point}>{point}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default ChatAnchorCard;

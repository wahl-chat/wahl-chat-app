import { feedItemHref } from '@/lib/daily/share';
import type { ChatAnchor, FeedItem } from '@/lib/firebase/firebase.types';

// Feed item ids: `bundestag_2026-07-10_v123`, `bundestag_2026-07-10_d90-top17`.
const FEED_ITEM_ID = /^[\w.~-]{1,200}$/;
const POLL_ID = /^\d{1,10}$/;

type Param = string | string[] | undefined;

function first(value: Param): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function pollId(value: unknown): number | undefined {
  const text = typeof value === 'number' ? String(value) : value;
  if (typeof text !== 'string' || !POLL_ID.test(text)) {
    return undefined;
  }
  const id = Number(text);
  return id > 0 && Number.isSafeInteger(id) ? id : undefined;
}

/** The anchor named by a chat URL's `feed_item` or `poll_id`. A feed item
 * wins: a vote's item names its poll too. */
export function chatAnchorFromParams(params: {
  feed_item?: Param;
  poll_id?: Param;
}): ChatAnchor | undefined {
  const feedItem = first(params.feed_item);
  if (feedItem && FEED_ITEM_ID.test(feedItem)) {
    return { feed_item_id: feedItem };
  }
  const poll = pollId(first(params.poll_id));
  return poll === undefined ? undefined : { poll_id: poll };
}

/** An anchor from untrusted input (request body, stored session), reduced to
 * exactly one well-formed key. */
export function sanitizeChatAnchor(value: unknown): ChatAnchor | undefined {
  if (!value || typeof value !== 'object') {
    return undefined;
  }
  const { feed_item_id, poll_id } = value as Record<string, unknown>;
  if (typeof feed_item_id === 'string' && FEED_ITEM_ID.test(feed_item_id)) {
    return { feed_item_id };
  }
  const poll = pollId(poll_id);
  return poll === undefined ? undefined : { poll_id: poll };
}

export type AnchorCard = {
  kind: 'Abstimmung' | 'Debatte';
  title: string;
  /** "10. Juli 2026"; null when unknown. */
  date: string | null;
  outcome: 'angenommen' | 'abgelehnt' | null;
  /** The item in the feed; null when there is none to go back to. */
  feedHref: string | null;
};

const longDay = new Intl.DateTimeFormat('de-DE', {
  day: 'numeric',
  month: 'long',
  year: 'numeric',
  timeZone: 'UTC',
});

/** What the chat's anchor card shows. A feed item that does not exist (or is
 * not published) shows nothing; a bare poll id a plain vote card. */
export function anchorCard(
  anchor: ChatAnchor,
  item: FeedItem | null | undefined,
): AnchorCard | null {
  if ('poll_id' in anchor) {
    return {
      kind: 'Abstimmung',
      title: `Abstimmung Nr. ${anchor.poll_id}`,
      date: null,
      outcome: null,
      feedHref: null,
    };
  }
  if (!item || item.status !== 'published') {
    return null;
  }
  return {
    kind: item.kind === 'vote' ? 'Abstimmung' : 'Debatte',
    title: item.content.de.headline,
    date: longDay.format(new Date(`${item.date}T00:00:00Z`)),
    outcome: item.vote?.outcome ?? null,
    feedHref: feedItemHref(item.id, item.region),
  };
}

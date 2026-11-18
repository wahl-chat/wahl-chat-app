import { plainStageName } from '@/lib/daily/procedures';
import { feedItemHref } from '@/lib/daily/share';
import type {
  ChatAnchor,
  FeedItem,
  StoredProcedure,
} from '@/lib/firebase/firebase.types';

// Feed item ids: `bundestag_2026-07-10_v123`, `bundestag_2026-07-10_d90-top17`.
export const FEED_ITEM_ID = /^[\w.~-]{1,200}$/;
const POLL_ID = /^\d{1,10}$/;
// DIP Vorgang ids.
const VORGANG_ID = /^\d{1,12}$/;

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

/** The anchor named by a chat URL's `feed_item`, `procedure` or `poll_id`.
 * A feed item wins: a vote's item names its poll too. */
export function chatAnchorFromParams(params: {
  feed_item?: Param;
  poll_id?: Param;
  procedure?: Param;
}): ChatAnchor | undefined {
  const feedItem = first(params.feed_item);
  if (feedItem && FEED_ITEM_ID.test(feedItem)) {
    return { feed_item_id: feedItem };
  }
  const procedure = first(params.procedure);
  if (procedure && VORGANG_ID.test(procedure)) {
    return { vorgang_id: procedure };
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
  const { feed_item_id, poll_id, vorgang_id } = value as Record<
    string,
    unknown
  >;
  if (typeof feed_item_id === 'string' && FEED_ITEM_ID.test(feed_item_id)) {
    return { feed_item_id };
  }
  if (typeof vorgang_id === 'string' && VORGANG_ID.test(vorgang_id)) {
    return { vorgang_id };
  }
  const poll = pollId(poll_id);
  return poll === undefined ? undefined : { poll_id: poll };
}

export type AnchorCard = {
  kind: 'Abstimmung' | 'Debatte' | 'Verfahren';
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

function published(item: FeedItem | null | undefined): item is FeedItem {
  return item?.status === 'published';
}

/** What the chat's anchor card shows. A feed item that does not exist (or is
 * not published) shows nothing, nor does an unknown procedure; a bare poll id
 * a plain vote card. `from` is the feed item a procedure chat was opened
 * from, the way back. */
export function anchorCard(
  anchor: ChatAnchor,
  item: FeedItem | null | undefined,
  procedure?: StoredProcedure | null,
  from?: FeedItem | null,
): AnchorCard | null {
  if ('vorgang_id' in anchor) {
    if (!procedure) {
      return null;
    }
    const day = procedure.latest_stage_on
      ? longDay.format(new Date(`${procedure.latest_stage_on}T00:00:00Z`))
      : null;
    return {
      kind: 'Verfahren',
      title: procedure.titel,
      date: procedure.latest_stage
        ? `Stand: ${[plainStageName(procedure.latest_stage), day].filter(Boolean).join(', ')}`
        : null,
      outcome: null,
      feedHref: published(from) ? feedItemHref(from.id, from.region) : null,
    };
  }
  if ('poll_id' in anchor) {
    return {
      kind: 'Abstimmung',
      title: `Abstimmung Nr. ${anchor.poll_id}`,
      date: null,
      outcome: null,
      feedHref: null,
    };
  }
  if (!published(item)) {
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

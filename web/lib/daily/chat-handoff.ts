import { sessionContextId } from '@/lib/chat-history';
import { GENERAL_CONTEXT_ID } from '@/lib/constants';
import type { ChatPreset, ChatSession } from '@/lib/firebase/firebase.types';

import type { DetailItem } from './items';

/** Shows the ask bars on the feed and in the detail view. */
export const FEED_CHAT_ENABLED = true;

/**
 * How a question from the feed opens the chat: `window` goes to the chat
 * page, `sheet` opens the chat in a sheet over the feed.
 */
export type FeedChatMode = 'window' | 'sheet';
export const FEED_CHAT_MODE: FeedChatMode = 'window';

/** The feed item id a detail item is stored under; a local preview has none. */
export function storedItemId(item: DetailItem): string | undefined {
  return item.kind === 'vote' ? item.vote.item_id : item.section.item_id;
}

/** The general chat with the question and the item as its anchor; `preset`
 * marks a button's fixed question. Without an item the question stands
 * alone. */
export function feedChatHref(
  item: DetailItem | undefined,
  question: string,
  preset?: ChatPreset,
): string {
  const params = new URLSearchParams({ q: question });
  const itemId = item && storedItemId(item);
  if (itemId) {
    params.set('feed_item', itemId);
    if (preset) params.set('preset', preset);
  }
  return `/chat?${params}`;
}

/** A new, empty general chat about the item, with its suggested questions. */
export function itemChatHref(item: DetailItem): string {
  const itemId = storedItemId(item);
  return itemId
    ? `/chat?${new URLSearchParams({ feed_item: itemId })}`
    : '/chat';
}

export function chatSessionHref(sessionId: string): string {
  return `/${GENERAL_CONTEXT_ID}/session/${sessionId}`;
}

/** A reader's chat about a feed item. */
export type ItemChat = { sessionId: string; title?: string };

/** The user's latest general chat that is about no item, by last
 * activity. History is newest first. */
export function latestGeneralChat(
  history: readonly ChatSession[],
): ItemChat | null {
  const session = history.find(
    (candidate) =>
      sessionContextId(candidate) === GENERAL_CONTEXT_ID && !candidate.anchor,
  );
  return session ? { sessionId: session.id, title: session.title } : null;
}

/** The procedures (DIP Vorgänge) an item belongs to. */
export function itemProcedureIds(item: DetailItem): string[] {
  const procedures =
    item.kind === 'vote' ? item.vote.procedures : item.section.procedures;
  return (procedures ?? []).map((procedure) => procedure.vorgang_id);
}

/** The user's last active general chat about the item: started from the
 * item itself or from the timeline of one of its procedures. History is
 * newest first. */
export function chatAbout(
  history: readonly ChatSession[],
  itemId: string | undefined,
  vorgangIds: readonly string[],
): ItemChat | null {
  const session = history.find((candidate) => {
    const anchor = candidate.anchor;
    if (!anchor || sessionContextId(candidate) !== GENERAL_CONTEXT_ID) {
      return false;
    }
    if ('feed_item_id' in anchor) return anchor.feed_item_id === itemId;
    return 'vorgang_id' in anchor && vorgangIds.includes(anchor.vorgang_id);
  });
  return session ? { sessionId: session.id, title: session.title } : null;
}

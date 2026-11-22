import type { ChatPreset } from '@/lib/firebase/firebase.types';

import type { DetailItem } from './items';

/** Shows the ask bars on the feed and in the detail view. */
export const FEED_CHAT_ENABLED = true;

function storedItemId(item: DetailItem): string | undefined {
  return item.kind === 'vote' ? item.vote.item_id : item.section.item_id;
}

/** The general chat with the question and the item as its anchor; `preset`
 * marks a button's fixed question. A local preview has no stored item, so it
 * goes without one. */
export function feedChatHref(
  item: DetailItem,
  question: string,
  preset?: ChatPreset,
): string {
  const params = new URLSearchParams({ q: question });
  const itemId = storedItemId(item);
  if (itemId) {
    params.set('feed_item', itemId);
    if (preset) params.set('preset', preset);
  }
  return `/chat?${params}`;
}

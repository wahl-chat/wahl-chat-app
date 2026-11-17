import type { DetailItem } from './items';

/** Shows the ask bars on the feed and in the detail view. */
export const FEED_CHAT_ENABLED = true;

function storedItemId(item: DetailItem): string | undefined {
  return item.kind === 'vote' ? item.vote.item_id : item.section.item_id;
}

/** The general chat with the question as typed and the item as its anchor.
 * A local preview has no stored item, so it goes without one. */
export function feedChatHref(item: DetailItem, question: string): string {
  const params = new URLSearchParams({ q: question });
  const itemId = storedItemId(item);
  if (itemId) {
    params.set('feed_item', itemId);
  }
  return `/chat?${params}`;
}

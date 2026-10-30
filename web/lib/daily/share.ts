import { toast } from 'sonner';
import { type DetailItem, itemTitle } from './items';
import { STATE_PARAM } from './region';

const ITEM_PARAM = 'item';

/** `DE` for the Bundestag, `ST` for `DE-ST`: the item's code in a selection. */
function stateCode(region: string): string {
  return region.replace(/^DE-/, '');
}

/**
 * The current view with `item` pointing at this card. An item resolves only
 * within the selected parliaments, and a selection restored from storage is
 * not in the URL, so the link always names the item's own parliament too.
 */
export function itemShareUrl(
  href: string,
  key: string,
  region: string,
): string {
  const url = new URL(href);
  url.searchParams.set(ITEM_PARAM, key);
  const code = stateCode(region).toLowerCase();
  const states = (url.searchParams.get(STATE_PARAM) ?? '')
    .split(',')
    .filter(Boolean);
  if (!states.includes(code)) {
    url.searchParams.set(STATE_PARAM, [...states, code].join(','));
  }
  return url.toString();
}

export async function shareItem(
  item: DetailItem,
  copiedMessage: string,
): Promise<void> {
  const url = itemShareUrl(window.location.href, item.key, item.digest.region);
  try {
    if (navigator.share) {
      await navigator.share({ title: itemTitle(item), url });
      return;
    }
    await navigator.clipboard.writeText(url);
    toast.success(copiedMessage);
  } catch {
    // The share sheet was dismissed.
  }
}

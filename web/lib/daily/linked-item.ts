import { getLinkedFeedDay } from '@/lib/firebase/firebase-server';
import { feedToDigests } from './editions';
import { type DetailItem, findItem } from './items';

/** The item a shared `?item=` link names, read from its day's edition. */
export async function getLinkedItem(
  itemKey: string,
): Promise<DetailItem | undefined> {
  const day = await getLinkedFeedDay(itemKey);
  return day ? findItem(feedToDigests(day), itemKey) : undefined;
}

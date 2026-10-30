import { type FeedInterest, setFeedInterest } from '@/lib/firebase/firebase';

const STORAGE_KEY = 'wahlchat-feed-interest';

/** The device's own answers, so a reload shows what was already answered
 * without reading Firestore (the rules allow no reads of other answers). */
export function readInterest(): Record<string, FeedInterest> {
  try {
    return JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? '{}');
  } catch {
    return {};
  }
}

/**
 * Feeds the ranking signal later. Never throws: a failed write must not break
 * the feed, and the local copy keeps the answer visible either way.
 */
export async function recordInterest(
  uid: string | undefined,
  itemId: string,
  value: FeedInterest,
): Promise<void> {
  try {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ ...readInterest(), [itemId]: value }),
    );
  } catch {
    // Storage blocked (private mode): the answer still goes to Firestore.
  }
  if (!uid) {
    return;
  }
  try {
    await setFeedInterest(uid, itemId, value);
  } catch (error) {
    console.error('[feed] failed to record interest:', error);
  }
}

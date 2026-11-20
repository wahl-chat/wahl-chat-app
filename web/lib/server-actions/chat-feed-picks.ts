'use server';

import { type FeedPick, feedPicks } from '@/lib/chat-feed';
import { getParliamentFeed } from '@/lib/firebase/firebase-server';

/** The Bundestag feed's latest two weeks, as the general chat offers them. */
export async function getChatFeedPicks(): Promise<FeedPick[]> {
  const page = await getParliamentFeed('bundestag');
  return feedPicks(page.items);
}

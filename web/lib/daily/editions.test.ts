import { describe, expect, it } from 'bun:test';
import type { FeedItem, ParliamentFeed } from '@/lib/firebase/firebase.types';
import feedFixture from '../../../firebase/firestore_data/emulator/feed.json';
import { feedToDigests } from './editions';
import { buildFeed, rankFeed } from './feed';
import { findItem, sectionItems, voteItems } from './items';
import { topicShortTitle } from './topics';

const FEED = feedFixture as unknown as ParliamentFeed;

describe('feedToDigests', () => {
  it('lays out every edition in its own order, keyed by item id', () => {
    const digests = feedToDigests(FEED);
    expect(digests.map((d) => d.id)).toEqual(FEED.editions.map((e) => e.id));
    for (const [i, digest] of digests.entries()) {
      const keys = [...sectionItems(digest), ...voteItems(digest)].map(
        (item) => item.key,
      );
      expect(keys).toEqual(FEED.editions[i].item_ids);
    }
  });

  it('shows the German text and keeps the facts', () => {
    const [digest] = feedToDigests(FEED);
    const item = FEED.items.find(
      (i) => i.id === FEED.editions[0].item_ids[0],
    ) as FeedItem;
    const [section] = digest.session?.sections ?? [];
    expect(section.headline).toBe(item.content.de.headline);
    expect(section.citations).toEqual(item.debate?.citations ?? []);
  });

  it('leaves retracted items out of the feed', () => {
    const gone = FEED.editions[0].item_ids[0];
    const feed: ParliamentFeed = {
      editions: FEED.editions,
      items: FEED.items.map((i) =>
        i.id === gone ? { ...i, status: 'retracted' } : i,
      ),
    };
    const digests = feedToDigests(feed);
    expect(findItem(digests, gone)).toBeUndefined();
  });
});

describe('debate topics', () => {
  it('lists a debate under each of its topics', () => {
    const id = FEED.editions[0].item_ids[0];
    const feed: ParliamentFeed = {
      editions: FEED.editions,
      items: FEED.items.map((i) =>
        i.id === id ? { ...i, topics: ['health_care', 'economy_finance'] } : i,
      ),
    };
    const shown = (topic: string) =>
      rankFeed(buildFeed([feedToDigests(feed)], 3650), [topic]).flatMap(
        (day) => [
          day.hot?.key,
          ...day.blocks.flatMap((b) => b.sections.map((s) => s.key)),
        ],
      );
    expect(shown('health_care')).toContain(id);
    expect(shown('economy_finance')).toContain(id);
    expect(shown('housing_rent')).not.toContain(id);
  });
});

describe('topic labels', () => {
  it('match the filter pills', () => {
    expect(topicShortTitle('health_care')).toBe('Gesundheit');
  });
});

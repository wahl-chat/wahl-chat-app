import { describe, expect, it } from 'bun:test';
import type { FeedItem, ParliamentFeed } from '@/lib/firebase/firebase.types';
import feedFixture from '../../../firebase/firestore_data/emulator/feed.json';
import de from '../../messages/de';
import en from '../../messages/en';
import { feedToDigests } from './editions';
import { buildFeed, rankFeed } from './feed';
import { DEFAULT_FILTER } from './filter';
import { findItem, sectionItems, voteItems } from './items';
import { DAILY_TOPIC_KEYS, topicKey } from './topics';

const FEED = feedFixture as unknown as ParliamentFeed;

describe('feedToDigests', () => {
  it('lays out every edition in its own order, keyed by item id', () => {
    const digests = feedToDigests(FEED, 'de');
    expect(digests.map((d) => d.id)).toEqual(FEED.editions.map((e) => e.id));
    for (const [i, digest] of digests.entries()) {
      const keys = [...sectionItems(digest), ...voteItems(digest)].map(
        (item) => item.key,
      );
      expect(keys).toEqual(FEED.editions[i].item_ids);
    }
  });

  it('shows the chosen language and keeps facts identical', () => {
    const [de] = feedToDigests(FEED, 'de');
    const [en] = feedToDigests(FEED, 'en');
    const item = FEED.items.find(
      (i) => i.id === FEED.editions[0].item_ids[0],
    ) as FeedItem;
    const [deSection] = de.session?.sections ?? [];
    const [enSection] = en.session?.sections ?? [];
    expect(deSection.headline).toBe(item.content.de.headline);
    expect(enSection.headline).toBe(item.content.en?.headline as string);
    expect(enSection.citations).toEqual(deSection.citations);
    expect(enSection.positions?.map((p) => p.party_id)).toEqual(
      deSection.positions?.map((p) => p.party_id),
    );
  });

  it('falls back to German where an item has no translation yet', () => {
    const untranslated: ParliamentFeed = {
      editions: FEED.editions,
      items: FEED.items.map((i) => ({ ...i, content: { de: i.content.de } })),
    };
    const [en] = feedToDigests(untranslated, 'en');
    expect(en.session?.sections[0].headline).toBe(
      FEED.items.find((i) => i.id === FEED.editions[0].item_ids[0])?.content.de
        .headline as string,
    );
  });

  it('shows the Union Fraktion with the CDU/CSU logo, in debates and votes', () => {
    const digests = feedToDigests(FEED, 'de');
    const positions = digests.flatMap((d) =>
      (d.session?.sections ?? []).flatMap((s) => s.positions ?? []),
    );
    const voteParties = digests.flatMap((d) =>
      (d.votes ?? []).flatMap((v) => v.parties),
    );
    for (const party of [...positions, ...voteParties]) {
      expect(party.logo_id).toBe(
        party.party_id === 'cdu' ? 'cdu_csu' : party.party_id,
      );
    }
    expect(positions.some((p) => p.party_id === 'cdu')).toBe(true);
    expect(voteParties.some((p) => p.party_id === 'cdu')).toBe(true);
  });

  it('passes the card video through, and none where an item has none', () => {
    const first = FEED.editions[0].item_ids[0];
    const card_video = {
      video_url: 'https://video/a.mp4',
      start: 3,
      poster_url: 'https://posters/a.webp',
      speaker: 'Anna',
      party_name: 'SPD',
    };
    const feed: ParliamentFeed = {
      editions: FEED.editions,
      items: FEED.items.map((i) =>
        i.id === first && i.debate
          ? { ...i, debate: { ...i.debate, card_video } }
          : i,
      ),
    };
    const [digest] = feedToDigests(feed, 'de');
    const [section, other] = digest.session?.sections ?? [];
    expect(section.card_video).toEqual(card_video);
    expect(other.card_video).toBeNull();
  });

  it('leaves retracted items out of the feed', () => {
    const gone = FEED.editions[0].item_ids[0];
    const feed: ParliamentFeed = {
      editions: FEED.editions,
      items: FEED.items.map((i) =>
        i.id === gone ? { ...i, status: 'retracted' } : i,
      ),
    };
    const digests = feedToDigests(feed, 'de');
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
      rankFeed(buildFeed([feedToDigests(feed, 'de')], 3650), {
        ...DEFAULT_FILTER,
        topics: [topic],
      }).flatMap((day) => [
        day.hot?.key,
        ...day.blocks.flatMap((b) => b.sections.map((s) => s.key)),
      ]);
    expect(shown('health_care')).toContain(id);
    expect(shown('economy_finance')).toContain(id);
    expect(shown('housing_rent')).not.toContain(id);
  });
});

describe('topic labels', () => {
  it('has a long and a short label for every topic in every language', () => {
    for (const catalog of [de, en]) {
      for (const key of DAILY_TOPIC_KEYS) {
        const label = catalog.topics[key as keyof typeof catalog.topics];
        expect(label.title).toBeTruthy();
        expect(label.short).toBeTruthy();
      }
    }
    expect(de.topics.health_care.short).toBe('Gesundheit');
    expect(en.topics.health_care.short).toBe('Health');
  });

  it('reads unknown topics as other', () => {
    expect(topicKey('health_care')).toBe('health_care');
    expect(topicKey('nonsense')).toBe('other');
  });
});

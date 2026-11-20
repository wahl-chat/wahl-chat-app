import { describe, expect, it } from 'bun:test';
import type {
  DailyDigest,
  DigestSessionSection,
  DigestVote,
} from '@/lib/firebase/firebase.types';
import { LOGO_IMAGE_URL } from '@/lib/seo';
import type { DetailItem } from './items';
import { itemShareMetadata } from './share-metadata';

const ORIGIN = 'https://dev.wahl.chat';
const FALLBACK = 'Debatten und Abstimmungen.';

const DIGEST: DailyDigest = {
  id: 'bundestag_2026-07-10',
  parliament: 'bundestag',
  parliament_name: 'Bundestag',
  region: 'DE',
  date: '2026-07-10',
  votes: [],
  session: null,
};

const SECTION: DigestSessionSection = {
  topic: 'economy_finance',
  headline: 'Debatte über Wohnungsbau',
  summary: 'Der Bundestag debattierte über Wohnungsbau.',
  agenda_items: [],
  citations: [],
  video_url: null,
};

const VOTE: DigestVote = {
  poll_id: 1,
  title: '',
  short_title: 'Bundeswehreinsatz verlängert',
  summary: 'Der Einsatz wird um ein Jahr verlängert.',
  topics: ['health_care'],
  outcome: null,
  citation_url: null,
  parties: [],
};

const voteItem: DetailItem = {
  kind: 'vote',
  key: 'bundestag_2026-07-10_v42',
  digest: DIGEST,
  vote: VOTE,
};

function debate(section: Partial<DigestSessionSection>): DetailItem {
  return {
    kind: 'section',
    key: 'bundestag_2026-07-10_d90-top17',
    digest: DIGEST,
    section: { ...SECTION, ...section },
  };
}

function imageUrl(item: DetailItem): string | undefined {
  const images = itemShareMetadata(item, ORIGIN, FALLBACK).openGraph?.images;
  const [first] = Array.isArray(images) ? images : [images];
  if (!first) {
    return undefined;
  }
  return typeof first === 'string' || first instanceof URL
    ? String(first)
    : String(first.url);
}

describe('itemShareMetadata', () => {
  it("leads with the vote's title and its Worum-ging-es text", () => {
    const { openGraph, twitter } = itemShareMetadata(
      voteItem,
      ORIGIN,
      FALLBACK,
    );
    expect(openGraph?.title).toEqual({
      absolute: 'Bundeswehreinsatz verlängert',
    });
    expect(openGraph?.description).toBe(
      'Der Einsatz wird um ein Jahr verlängert.',
    );
    expect(twitter?.title).toBe('Bundeswehreinsatz verlängert');
  });

  it("shows a vote's chamber, drawn by this deployment", () => {
    expect(imageUrl(voteItem)).toBe(
      'https://dev.wahl.chat/api/og/feed/bundestag_2026-07-10_v42',
    );
  });

  it("leads with the debate's headline and the text under it", () => {
    const { openGraph } = itemShareMetadata(debate({}), ORIGIN, FALLBACK);
    expect(openGraph?.title).toEqual({ absolute: 'Debatte über Wohnungsbau' });
    expect(openGraph?.description).toBe(
      'Der Bundestag debattierte über Wohnungsbau.',
    );
  });

  it("shows a debate's video poster", () => {
    const card_video = {
      video_url: 'https://example.org/v.mp4',
      start: 12,
      poster_url: 'https://storage.example.org/poster.webp',
      speaker: null,
      party_name: null,
    };
    expect(imageUrl(debate({ card_video }))).toBe(
      'https://storage.example.org/poster.webp',
    );
  });

  it('falls back to the logo for a debate without a poster', () => {
    expect(imageUrl(debate({}))).toBe(LOGO_IMAGE_URL);
    const card_video = {
      video_url: 'https://example.org/v.mp4',
      start: 0,
      poster_url: null,
      speaker: null,
      party_name: null,
    };
    expect(imageUrl(debate({ card_video }))).toBe(LOGO_IMAGE_URL);
  });

  it('cuts a long text at a word', () => {
    const summary = `${'Wort '.repeat(100)}Ende`;
    const description = itemShareMetadata(debate({ summary }), ORIGIN, FALLBACK)
      .openGraph?.description;
    expect(description?.length).toBeLessThanOrEqual(300);
    expect(description?.endsWith('Wort…')).toBe(true);
  });

  it('uses the feed description when the item has no text', () => {
    expect(
      itemShareMetadata(debate({ summary: '' }), ORIGIN, FALLBACK).openGraph
        ?.description,
    ).toBe(FALLBACK);
  });

  it("names no og:url, which would lose the link's item", () => {
    expect(
      itemShareMetadata(voteItem, ORIGIN, FALLBACK).openGraph?.url,
    ).toBeUndefined();
  });
});

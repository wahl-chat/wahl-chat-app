import { describe, expect, it } from 'bun:test';
import type {
  DailyDigest,
  DigestSessionSection,
  DigestVote,
} from '@/lib/firebase/firebase.types';
import { itemTeaser, openingParty } from './items';

const SECTION: DigestSessionSection = {
  topic: 'economy_finance',
  headline: '',
  summary: '',
  agenda_items: [],
  citations: [],
  video_url: null,
};

describe('openingParty', () => {
  it('prefers the recorded opener', () => {
    expect(openingParty({ ...SECTION, opened_by: 'spd' })).toBe('spd');
  });

  it('falls back to the first cited speech, mapped to its Fraktion', () => {
    const citations = [{ title: '', url: '', party_id: 'csu' }];
    expect(openingParty({ ...SECTION, citations })).toBe('cdu');
  });

  it('is null when nothing says who opened', () => {
    expect(openingParty(SECTION)).toBeNull();
  });
});

const DIGEST: DailyDigest = {
  id: 'bundestag_2026-07-10',
  parliament: 'bundestag',
  parliament_name: 'Bundestag',
  region: 'DE',
  date: '2026-07-10',
  votes: [],
  session: null,
};

const VOTE: DigestVote = {
  poll_id: 1,
  title: '',
  short_title: '',
  summary: null,
  topics: ['health_care'],
  outcome: null,
  citation_url: null,
  parties: [],
};

describe('itemTeaser', () => {
  it("is a debate's summary", () => {
    const section = { ...SECTION, summary: 'Worum es ging.' };
    expect(
      itemTeaser({ kind: 'section', key: 'k', digest: DIGEST, section }),
    ).toBe('Worum es ging.');
  });

  it("prefers a vote's own summary over the source's description", () => {
    const vote = { ...VOTE, summary: 'Kurz.', description: 'Lang.' };
    expect(itemTeaser({ kind: 'vote', key: 'k', digest: DIGEST, vote })).toBe(
      'Kurz.',
    );
  });

  it("falls back to the source's description of the motion", () => {
    const vote = { ...VOTE, description: 'Lang.' };
    expect(itemTeaser({ kind: 'vote', key: 'k', digest: DIGEST, vote })).toBe(
      'Lang.',
    );
  });

  it('is null when there is nothing to tease', () => {
    expect(
      itemTeaser({ kind: 'vote', key: 'k', digest: DIGEST, vote: VOTE }),
    ).toBeNull();
  });
});

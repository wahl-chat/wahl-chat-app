import { describe, expect, it } from 'bun:test';
import type {
  DailyDigest,
  DigestSessionSection,
  DigestVote,
} from '@/lib/firebase/firebase.types';
import { debateForVote, itemTeaser, openingParty } from './items';

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

describe('debateForVote', () => {
  const debate = (drucksachen?: string[], item_id?: string) => ({
    ...SECTION,
    drucksachen,
    item_id,
  });
  const voteItem = (
    sections: DigestSessionSection[],
    drucksachen?: string[],
  ) => {
    const digest = {
      ...DIGEST,
      session: { protocols: [], sections },
    };
    return {
      kind: 'vote' as const,
      key: 'v',
      digest,
      vote: { ...VOTE, drucksachen },
    };
  };

  it('finds the debate that shares a Drucksache with the vote', () => {
    const item = voteItem(
      [debate(['21/1'], 'other'), debate(['21/2', '21/3'], 'debated')],
      ['21/3'],
    );
    expect(debateForVote(item)?.key).toBe('debated');
  });

  it('is null when no debate shares a Drucksache', () => {
    expect(debateForVote(voteItem([debate(['21/1'], 'd')], ['21/9']))).toBe(
      null,
    );
  });

  it('is null while the Drucksachen are unknown', () => {
    expect(debateForVote(voteItem([debate(undefined, 'd')], ['21/1']))).toBe(
      null,
    );
    expect(debateForVote(voteItem([debate(['21/1'], 'd')]))).toBe(null);
  });

  it('is null on a day without a sitting', () => {
    expect(debateForVote(voteItem([], ['21/1']))).toBe(null);
  });
});

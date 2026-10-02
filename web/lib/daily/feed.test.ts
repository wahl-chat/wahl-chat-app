import { describe, expect, it } from 'bun:test';
import type {
  DailyDigest,
  DigestParliamentId,
} from '@/lib/firebase/firebase.types';
import { buildFeed, windowedDigests } from './feed';
import { parliamentsFor, parseStateParam, stateFromGeo } from './region';

function digest(parliament: DigestParliamentId, date: string): DailyDigest {
  return {
    id: `${parliament}_${date}`,
    parliament,
    parliament_name: parliament,
    region: 'DE',
    date,
    votes: [],
    session: null,
  };
}

describe('windowedDigests', () => {
  it('ends the window on the latest digest, not today', () => {
    const kept = windowedDigests([
      digest('landtag_st', '2026-07-10'),
      digest('landtag_st', '2026-06-27'),
      digest('landtag_st', '2026-06-26'),
    ]);
    expect(kept.map((d) => d.date)).toEqual(['2026-07-10', '2026-06-27']);
  });
});

describe('buildFeed', () => {
  it('merges parliaments into days, newest first, Bundestag first', () => {
    const feed = buildFeed([
      [digest('landtag_bw', '2026-09-24')],
      [digest('bundestag', '2026-09-25'), digest('bundestag', '2026-09-24')],
    ]);
    expect(feed.map((d) => d.date)).toEqual(['2026-09-25', '2026-09-24']);
    expect(feed[1].digests.map((d) => d.parliament)).toEqual([
      'bundestag',
      'landtag_bw',
    ]);
  });
});

describe('region', () => {
  it('maps Vercel geo headers to a covered state', () => {
    expect(stateFromGeo('DE', 'ST')).toBe('ST');
    expect(stateFromGeo('DE', 'bw')).toBe('BW');
    expect(stateFromGeo('DE', 'BY')).toBe('none');
    expect(stateFromGeo('AT', 'ST')).toBe('none');
    expect(stateFromGeo(null, null)).toBe('none');
  });

  it('parses the land param and leaves unknown values to geo', () => {
    expect(parseStateParam('st')).toBe('ST');
    expect(parseStateParam('none')).toBe('none');
    expect(parseStateParam('BY')).toBeUndefined();
    expect(parseStateParam(undefined)).toBeUndefined();
  });

  it('always includes the Bundestag', () => {
    expect(parliamentsFor('none')).toEqual(['bundestag']);
    expect(parliamentsFor('BW')).toEqual(['bundestag', 'landtag_bw']);
  });
});

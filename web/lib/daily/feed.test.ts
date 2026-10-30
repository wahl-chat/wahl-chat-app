import { describe, expect, it } from 'bun:test';
import type {
  DailyDigest,
  DigestParliamentId,
  DigestSessionSection,
  DigestVote,
} from '@/lib/firebase/firebase.types';
import {
  buildFeed,
  dayHeat,
  feedLists,
  rankFeed,
  windowedDigests,
} from './feed';
import { parliamentsFor, parseStateParam } from './region';
import { editionIdOf, pageStart } from './window';

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

  it('keeps every digest of a server-cut list, older slices included', () => {
    const feed = buildFeed(
      [[digest('bundestag', '2026-10-23'), digest('bundestag', '2026-09-03')]],
      null,
    );
    expect(feed.map((d) => d.date)).toEqual(['2026-10-23', '2026-09-03']);
  });
});

describe('pageStart', () => {
  it('spans fourteen days ending on the anchor edition', () => {
    expect(pageStart('2026-10-23')).toBe('2026-10-10');
    expect(pageStart('2026-03-01')).toBe('2026-02-16');
  });
});

describe('region', () => {
  it('parses a comma-separated land param, keeping selectable codes only', () => {
    // No Landtag is covered yet, so a stored or shared Land drops out.
    expect(parseStateParam('de,st,BW,by,xx')).toEqual(['DE']);
    expect(parseStateParam('de,de')).toEqual(['DE']);
    expect(parseStateParam('st')).toBeUndefined();
  });

  it('leaves an empty or unusable param to the stored choice or default', () => {
    expect(parseStateParam('')).toBeUndefined();
    expect(parseStateParam('by')).toBeUndefined();
    expect(parseStateParam(undefined)).toBeUndefined();
  });

  it('shows only the selected parliaments, Bundestag first', () => {
    expect(parliamentsFor(['DE'])).toEqual(['bundestag']);
    expect(parliamentsFor(['BW', 'DE'])).toEqual(['bundestag']);
  });
});

function section(
  topic: string,
  heat: number | null,
  minutes: number | null,
): DigestSessionSection {
  return {
    topic,
    headline: `${topic} ${heat}`,
    summary: '',
    agenda_items: [],
    citations: [],
    video_url: null,
    heat,
    debate_minutes: minutes,
  };
}

function vote(pollId: number, topics: string[]): DigestVote {
  return {
    poll_id: pollId,
    title: '',
    short_title: `Vote ${pollId}`,
    summary: null,
    topics,
    outcome: 'angenommen',
    citation_url: null,
    parties: [],
  };
}

function sitting(
  parliament: DigestParliamentId,
  date: string,
  sections: DigestSessionSection[],
  votes: DigestVote[] = [],
): DailyDigest {
  return {
    ...digest(parliament, date),
    votes,
    session: { protocols: [], sections },
  };
}

describe('dayHeat', () => {
  it('rescales against the hottest section of the day, across parliaments', () => {
    // Pooled across parliaments, only the day's hottest debate keeps 5.
    const [day] = rankFeed(
      buildFeed([
        [sitting('bundestag', '2026-09-08', [section('health_care', 4, 60)])],
        [sitting('landtag_st', '2026-09-08', [section('housing_rent', 5, 10)])],
      ]),
      [],
    );
    expect([...day.heat.values()].sort()).toEqual([4, 5]);
  });

  it('is empty when no section carries a rating', () => {
    expect(dayHeat([]).size).toBe(0);
  });
});

describe('rankFeed', () => {
  const days = buildFeed([
    [
      sitting(
        'bundestag',
        '2026-09-08',
        [
          section('housing_rent', 2, 30),
          section('economy_finance', 5, 90),
          section('climate_environment', 4, 60),
        ],
        [vote(1, ['health_care']), vote(2, ['climate_environment'])],
      ),
      sitting(
        'bundestag',
        '2026-09-03',
        [section('health_care', 5, 200)],
        [vote(3, ['economy_finance'])],
      ),
    ],
  ]);

  it('leads each day with its own most heated debate', () => {
    const [latest, earlier] = rankFeed(days, []);
    expect(latest.hot?.section.topic).toBe('economy_finance');
    // A hotter, longer debate from an earlier day does not cross days.
    expect(earlier.hot?.section.topic).toBe('health_care');
  });

  it('sorts the rest of the day by prior and leaves the hot one out', () => {
    const [latest] = rankFeed(days, []);
    expect(latest.blocks[0].sections.map((s) => s.section.topic)).toEqual([
      'climate_environment',
      'housing_rent',
    ]);
  });

  it('matches a vote on the hot topic from an earlier day when needed', () => {
    const [latest] = rankFeed(days, []);
    expect(latest.match?.vote.poll_id).toBe(3);
    // An earlier-day match stays in its own day's group as well.
    expect(latest.blocks[0].votes.map((v) => v.vote.poll_id)).toEqual([1, 2]);
  });

  it('prefers a same-day match and does not show it twice', () => {
    const [latest] = rankFeed(days, ['climate_environment']);
    expect(latest.hot?.section.topic).toBe('climate_environment');
    expect(latest.match?.vote.poll_id).toBe(2);
    expect(latest.blocks).toEqual([]);
  });
});

describe('feedLists', () => {
  const stored = {
    bundestag: [
      digest('bundestag', '2026-07-10'),
      digest('bundestag', '2026-07-09'),
    ],
    landtag_st: [digest('landtag_st', '2026-07-08')],
    landtag_bw: [],
  };

  it('keeps stored days in the feed when a preview is weeks newer', () => {
    const days = buildFeed(
      feedLists(stored, ['bundestag'], [digest('bundestag', '2026-09-08')]),
    );
    expect(days.map((d) => d.date)).toEqual([
      '2026-09-08',
      '2026-07-10',
      '2026-07-09',
    ]);
  });

  it('replaces the stored digest a preview shares an id with', () => {
    const preview = { ...digest('bundestag', '2026-07-10'), votes: [] };
    const days = buildFeed(feedLists(stored, ['bundestag'], [preview]));
    expect(days[0].digests).toEqual([preview]);
  });

  it('leaves out previews of parliaments not shown', () => {
    const lists = feedLists(
      stored,
      ['bundestag'],
      [digest('landtag_st', '2026-09-08')],
    );
    expect(lists.flat().map((d) => d.parliament)).not.toContain('landtag_st');
  });
});

describe('editionIdOf', () => {
  it('finds the sitting day of an item key', () => {
    expect(editionIdOf('bundestag_2026-07-10_v6421')).toBe(
      'bundestag_2026-07-10',
    );
    expect(editionIdOf('bundestag_2026-07-10_d90-top17')).toBe(
      'bundestag_2026-07-10',
    );
    expect(editionIdOf('landtag_st_2026-06-18_v12')).toBe(
      'landtag_st_2026-06-18',
    );
  });

  it('rejects keys that name no edition', () => {
    expect(editionIdOf('bundestag_2026-07-1')).toBeNull();
    expect(editionIdOf('../feed_items/x')).toBeNull();
    expect(editionIdOf('landtag_by_2026-07-10_v1')).toBeNull();
  });
});

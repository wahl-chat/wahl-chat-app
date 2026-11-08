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
  heatExplanation,
  isPendingDay,
  isWaitingDigest,
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
  interjections: number | null,
  minutes: number | null,
  drucksachen: string[] = [],
): DigestSessionSection {
  return {
    topic,
    drucksachen,
    interjections,
    headline: `${topic} ${interjections}`,
    summary: '',
    agenda_items: [],
    citations: [],
    video_url: null,
    debate_minutes: minutes,
  };
}

function vote(
  pollId: number,
  topics: string[],
  drucksachen: string[] = [],
): DigestVote {
  return {
    poll_id: pollId,
    drucksachen,
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

/** Flames per section in the given order; 0 for a section without any. */
function heatOf(sections: DigestSessionSection[]): number[] {
  const [day] = rankFeed(
    buildFeed([[sitting('bundestag', '2026-07-10', sections)]]),
    [],
  );
  // Sections without an item id are keyed by their place in the digest.
  return sections.map(
    (_, i) => day.heat.get(`bundestag_2026-07-10~s${i}`) ?? 0,
  );
}

describe('dayHeat', () => {
  it('spreads the day from its quietest debate to its busiest', () => {
    // Interjections per minute: 1.67, 1.42, 0.97, 0.33 and 0.
    expect(
      heatOf([
        section('climate_environment', 100, 60),
        section('health_care', 143, 101),
        section('economy_finance', 120, 124),
        section('education_research', 13, 40),
        section('other', 0, 42),
      ]),
    ).toEqual([5, 4, 3, 2, 1]);
  });

  it('rates debates against each other, not against a fixed scale', () => {
    // A rowdy day's quietest debate still shows 1 flame, its middle one 3.
    expect(
      heatOf([
        section('health_care', 60, 60),
        section('housing_rent', 120, 60),
        section('other', 180, 60),
      ]),
    ).toEqual([1, 3, 5]);
  });

  it('compares across the parliaments shown that day', () => {
    const [day] = rankFeed(
      buildFeed([
        [sitting('bundestag', '2026-09-08', [section('health_care', 30, 60)])],
        [
          sitting('landtag_st', '2026-09-08', [
            section('housing_rent', 10, 10),
          ]),
        ],
      ]),
      [],
    );
    expect([...day.heat.values()].sort()).toEqual([1, 5]);
  });

  it('gives no flames when there is nothing to compare', () => {
    expect(dayHeat([]).size).toBe(0);
    expect(heatOf([section('health_care', 30, 60)])).toEqual([0]);
    expect(
      heatOf([section('health_care', 30, 60), section('other', 60, 120)]),
    ).toEqual([0, 0]);
  });

  it('leaves a debate without a count out of the comparison', () => {
    expect(
      heatOf([
        section('health_care', 30, 60),
        section('other', null, 60),
        section('housing_rent', 90, 60),
      ]),
    ).toEqual([1, 0, 5]);
  });
});

describe('rankFeed', () => {
  const days = buildFeed([
    [
      sitting(
        'bundestag',
        '2026-09-08',
        [
          // Per minute: 0.33, 1.0 and 0.5.
          section('housing_rent', 10, 30),
          section('economy_finance', 90, 90, ['21/100']),
          section('climate_environment', 30, 60, ['21/200']),
        ],
        [
          vote(1, ['health_care']),
          vote(2, ['climate_environment'], ['21/200', '21/201']),
          // Same topic as the hot debate, but another motion.
          vote(4, ['economy_finance'], ['21/999']),
        ],
      ),
      sitting(
        'bundestag',
        '2026-09-03',
        [section('health_care', 400, 200)],
        // The hot debate's own Drucksache, voted on another day.
        [vote(3, ['economy_finance'], ['21/100'])],
      ),
    ],
  ]);

  it('leads each day with its own most heated debate', () => {
    const [latest, earlier] = rankFeed(days, []);
    expect(latest.hot?.section.topic).toBe('economy_finance');
    // A hotter debate from an earlier day does not cross days.
    expect(earlier.hot?.section.topic).toBe('health_care');
  });

  it('picks the Hot Topic by rate alone, not by length', () => {
    const [day] = rankFeed(
      buildFeed([
        [
          sitting('bundestag', '2026-07-10', [
            section('economy_finance', 120, 124),
            section('climate_environment', 100, 60),
          ]),
        ],
      ]),
      [],
    );
    expect(day.hot?.section.topic).toBe('climate_environment');
  });

  it('crowns no Hot Topic on a day without counts', () => {
    const [day] = rankFeed(
      buildFeed([
        [
          sitting('bundestag', '2026-07-10', [
            section('economy_finance', null, 124),
            section('climate_environment', null, 60),
          ]),
        ],
      ]),
      [],
    );
    expect(day.hot).toBeNull();
    expect(day.blocks[0].sections).toHaveLength(2);
  });

  it('sorts the rest of the day by heat and leaves the hot one out', () => {
    const [latest] = rankFeed(days, []);
    expect(latest.blocks[0].sections.map((s) => s.section.topic)).toEqual([
      'climate_environment',
      'housing_rent',
    ]);
  });

  it('pairs no vote by topic alone, nor from another day', () => {
    const [latest, earlier] = rankFeed(days, []);
    expect(latest.hot?.section.topic).toBe('economy_finance');
    expect(latest.match).toBeNull();
    expect(latest.blocks[0].votes.map((v) => v.vote.poll_id)).toEqual([
      1, 2, 4,
    ]);
    expect(earlier.match).toBeNull();
  });

  it('pairs the same-day vote on the debated Drucksache, shown once', () => {
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

describe('isPendingDay', () => {
  /** A day stored with its protocol but no debate or vote yet. */
  function waiting(date: string): DailyDigest {
    return {
      ...digest('bundestag', date),
      session: {
        protocols: [{ protocol_id: '21/105', pdf_url: null }],
        sections: [],
      },
    };
  }

  it('picks the days stored before any of their debates or votes', () => {
    const days = buildFeed(
      [
        [
          waiting('2026-11-05'),
          sitting('bundestag', '2026-10-16', [section('housing_rent', 5, 10)]),
          sitting('bundestag', '2026-10-15', [], [vote(1, ['health_care'])]),
        ],
      ],
      null,
    );
    expect(days.filter(isPendingDay).map((d) => d.date)).toEqual([
      '2026-11-05',
    ]);
    expect(isWaitingDigest(waiting('2026-11-05'))).toBe(true);
  });

  it('keeps a day another parliament has items for', () => {
    const [day] = buildFeed([
      [waiting('2026-11-05')],
      [sitting('landtag_st', '2026-11-05', [section('housing_rent', 5, 10)])],
    ]);
    expect(isPendingDay(day)).toBe(false);
  });

  it('never counts a day a topic filter empties', () => {
    const days = buildFeed([
      [sitting('bundestag', '2026-10-16', [section('housing_rent', 5, 10)])],
    ]);
    expect(days.filter(isPendingDay)).toEqual([]);
    const [day] = rankFeed(days, ['health_care']);
    expect(day.hot).toBeNull();
    expect(day.blocks).toEqual([]);
  });
});

describe('heatExplanation', () => {
  it('says what is counted, then where the debate stands that day', () => {
    const [counted, hottest] = heatExplanation(5);
    expect(counted).toContain('Zwischenrufe');
    expect(hottest).toBe('5 von 5: die hitzigste Debatte dieses Sitzungstags.');
    expect(heatExplanation(1)[1]).toBe(
      '1 von 5: die ruhigste Debatte dieses Sitzungstags.',
    );
    expect(heatExplanation(3)[1]).toBe(
      '3 von 5, verglichen mit den anderen Debatten dieses Sitzungstags.',
    );
  });
});

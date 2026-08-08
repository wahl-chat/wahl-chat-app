import { describe, expect, it } from 'bun:test';
import {
  getNextUpcomingElection,
  isUpcomingElection,
  splitElectionsByDate,
} from '@/lib/elections';
import type { Context } from '@/lib/firebase/firebase.types';

const NOW = new Date('2026-08-08T12:00:00Z');

function election(context_id: string, date: Date | null): Context {
  return {
    context_id,
    name: context_id,
    icon_url: '',
    type: 'election',
    date,
    location_name: '',
    is_active: true,
    supports_swiper: false,
    supports_voting_behavior: false,
  };
}

describe('isUpcomingElection', () => {
  it('treats a future election as upcoming', () => {
    expect(
      isUpcomingElection(election('future', new Date('2026-09-06')), NOW),
    ).toBe(true);
  });

  it('keeps an election upcoming inside the 5-day buffer', () => {
    // Results are the most-searched thing right after polls close, so a just-held
    // election must not be demoted on election night.
    expect(
      isUpcomingElection(election('yesterday', new Date('2026-08-07')), NOW),
    ).toBe(true);
    expect(
      isUpcomingElection(election('4-days-ago', new Date('2026-08-04')), NOW),
    ).toBe(true);
  });

  it('treats an election past the buffer as concluded', () => {
    expect(
      isUpcomingElection(election('6-days-ago', new Date('2026-08-02')), NOW),
    ).toBe(false);
  });

  it('treats an undated context as upcoming', () => {
    expect(isUpcomingElection(election('undated', null), NOW)).toBe(true);
  });

  it('treats an unparseable date as upcoming rather than hiding the context', () => {
    const broken = { ...election('broken', null), date: 'not-a-date' as never };
    expect(isUpcomingElection(broken, NOW)).toBe(true);
  });

  it('accepts a date that arrives as a string', () => {
    const asString = {
      ...election('string', null),
      date: '2026-09-06' as never,
    };
    expect(isUpcomingElection(asString, NOW)).toBe(true);
  });
});

describe('splitElectionsByDate', () => {
  it('sorts upcoming nearest-first and puts undated contexts last', () => {
    const { upcoming, past } = splitElectionsByDate(
      [
        election('later', new Date('2026-11-01')),
        election('undated', null),
        election('soon', new Date('2026-09-06')),
        election('done', new Date('2025-02-23')),
      ],
      NOW,
    );

    expect(upcoming.map((c) => c.context_id)).toEqual([
      'soon',
      'later',
      'undated',
    ]);
    expect(past.map((c) => c.context_id)).toEqual(['done']);
  });

  it('handles an all-concluded list', () => {
    const { upcoming, past } = splitElectionsByDate(
      [
        election('a', new Date('2025-02-23')),
        election('b', new Date('2026-03-08')),
      ],
      NOW,
    );

    expect(upcoming).toEqual([]);
    expect(past).toHaveLength(2);
  });

  it('does not mutate the input array order', () => {
    const contexts = [
      election('later', new Date('2026-11-01')),
      election('soon', new Date('2026-09-06')),
    ];
    splitElectionsByDate(contexts, NOW);

    expect(contexts.map((c) => c.context_id)).toEqual(['later', 'soon']);
  });
});

describe('getNextUpcomingElection', () => {
  it('returns the nearest upcoming election', () => {
    const next = getNextUpcomingElection(
      [
        election('later', new Date('2026-11-01')),
        election('soon', new Date('2026-09-06')),
        election('done', new Date('2025-02-23')),
      ],
      NOW,
    );

    expect(next?.context_id).toBe('soon');
  });

  it('returns undefined when every election has concluded', () => {
    // The steady state between elections — / must still render.
    expect(
      getNextUpcomingElection([election('done', new Date('2025-02-23'))], NOW),
    ).toBeUndefined();
  });

  it('returns undefined for an empty list', () => {
    expect(getNextUpcomingElection([], NOW)).toBeUndefined();
  });
});

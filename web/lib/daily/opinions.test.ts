import { describe, expect, it } from 'bun:test';
import {
  EMPTY_COUNTS,
  EMPTY_OPINION,
  type FeedOpinion,
  MIN_PUBLISHED_ANSWERS,
  applyIncrements,
  hasIncrements,
  isAbandoned,
  isEmptyOpinion,
  nextOpinion,
  opinionIncrements,
  parseFeedOpinionBody,
  publishedCounts,
  scoreOf,
  toFeedOpinion,
  toOpinionCounts,
  toPublishedCounts,
} from './opinions';

const ITEM = 'bundestag_2026-07-10_v6601';

describe('parseFeedOpinionBody', () => {
  it('accepts a vote', () => {
    expect(
      parseFeedOpinionBody({ item_id: ITEM, target: 'vote', value: 'accept' }),
    ).toEqual({
      ok: true,
      data: {
        itemId: ITEM,
        target: { kind: 'vote' },
        value: 'accept',
        consent: false,
      },
    });
  });

  it('accepts a position with consent', () => {
    const parsed = parseFeedOpinionBody({
      item_id: ITEM,
      target: 'position',
      party_id: 'gruene',
      value: 'down',
      consent: true,
    });
    expect(parsed).toEqual({
      ok: true,
      data: {
        itemId: ITEM,
        target: { kind: 'position', partyId: 'gruene' },
        value: 'down',
        consent: true,
      },
    });
  });

  it('accepts taking an opinion back', () => {
    const parsed = parseFeedOpinionBody({
      item_id: ITEM,
      target: 'vote',
      value: null,
    });
    expect(parsed.ok && parsed.data.value).toBeNull();
  });

  it('only counts a literal true as consent', () => {
    const parsed = parseFeedOpinionBody({
      item_id: ITEM,
      target: 'vote',
      value: 'reject',
      consent: 'yes',
    });
    expect(parsed.ok && parsed.data.consent).toBe(false);
  });

  it.each([
    ['no body', null],
    ['a missing item id', { target: 'vote', value: 'accept' }],
    [
      'an item id with a path',
      { item_id: 'a/b', target: 'vote', value: 'accept' },
    ],
    [
      'an overlong item id',
      { item_id: 'x'.repeat(121), target: 'vote', value: 'accept' },
    ],
    ['an unknown target', { item_id: ITEM, target: 'speech', value: 'up' }],
    [
      'a position value on a vote',
      { item_id: ITEM, target: 'vote', value: 'up' },
    ],
    [
      'a vote value on a position',
      { item_id: ITEM, target: 'position', party_id: 'spd', value: 'accept' },
    ],
    [
      'a position without a party',
      { item_id: ITEM, target: 'position', value: 'up' },
    ],
    [
      'a party id with a dot',
      { item_id: ITEM, target: 'position', party_id: 'a.b', value: 'up' },
    ],
    ['a missing value', { item_id: ITEM, target: 'vote' }],
  ])('rejects %s', (_, body) => {
    expect(parseFeedOpinionBody(body).ok).toBe(false);
  });
});

describe('nextOpinion', () => {
  it('sets and clears the vote', () => {
    const voted = nextOpinion(EMPTY_OPINION, { kind: 'vote' }, 'accept');
    expect(voted.vote).toBe('accept');
    expect(nextOpinion(voted, { kind: 'vote' }, null).vote).toBeNull();
  });

  it('sets and removes one position, leaving the others', () => {
    const start: FeedOpinion = { vote: null, positions: { spd: 'up' } };
    const added = nextOpinion(
      start,
      { kind: 'position', partyId: 'afd' },
      'down',
    );
    expect(added.positions).toEqual({ spd: 'up', afd: 'down' });
    const removed = nextOpinion(
      added,
      { kind: 'position', partyId: 'spd' },
      null,
    );
    expect(removed.positions).toEqual({ afd: 'down' });
    // The input is not mutated.
    expect(start.positions).toEqual({ spd: 'up' });
  });
});

describe('opinionIncrements', () => {
  const vote = (value: 'accept' | 'reject' | null): FeedOpinion => ({
    vote: value,
    positions: {},
  });

  it('counts a first vote', () => {
    expect(opinionIncrements(vote(null), vote('accept')).vote).toEqual({
      accept: 1,
    });
  });

  it('moves a changed vote', () => {
    expect(opinionIncrements(vote('accept'), vote('reject')).vote).toEqual({
      accept: -1,
      reject: 1,
    });
  });

  it('takes a withdrawn vote back', () => {
    expect(opinionIncrements(vote('reject'), vote(null)).vote).toEqual({
      reject: -1,
    });
  });

  it('lists nothing when nothing changed', () => {
    const same: FeedOpinion = { vote: 'accept', positions: { spd: 'up' } };
    expect(hasIncrements(opinionIncrements(same, same))).toBe(false);
  });

  it('moves positions per party', () => {
    const before: FeedOpinion = {
      vote: null,
      positions: { spd: 'up', afd: 'down', cdu: 'up' },
    };
    const after: FeedOpinion = {
      vote: null,
      positions: { spd: 'down', cdu: 'up', linke: 'up' },
    };
    expect(opinionIncrements(before, after).positions).toEqual({
      spd: { up: -1, down: 1 },
      afd: { down: -1 },
      linke: { up: 1 },
    });
  });

  it('withdraws everything back to empty', () => {
    const before: FeedOpinion = { vote: 'accept', positions: { spd: 'up' } };
    const counts = applyIncrements(
      applyIncrements(EMPTY_COUNTS, opinionIncrements(EMPTY_OPINION, before)),
      opinionIncrements(before, EMPTY_OPINION),
    );
    expect(counts).toEqual({
      vote: { accept: 0, reject: 0 },
      positions: { spd: { up: 0, down: 0 } },
    });
  });
});

describe('applyIncrements', () => {
  it('adds to existing counts without mutating them', () => {
    const counts = {
      vote: { accept: 796, reject: 488 },
      positions: { spd: { up: 31, down: 0 } },
    };
    const next = applyIncrements(counts, {
      vote: { accept: -1, reject: 1 },
      positions: { spd: { down: 1 }, afd: { up: 1 } },
    });
    expect(next).toEqual({
      vote: { accept: 795, reject: 489 },
      positions: { spd: { up: 31, down: 1 }, afd: { up: 1, down: 0 } },
    });
    expect(counts.vote.accept).toBe(796);
  });
});

describe('toOpinionCounts / toFeedOpinion', () => {
  it('reads a missing doc as empty', () => {
    expect(toOpinionCounts(undefined)).toEqual(EMPTY_COUNTS);
    expect(toFeedOpinion(undefined)).toEqual(EMPTY_OPINION);
  });

  it('ignores malformed fields', () => {
    expect(
      toOpinionCounts({
        vote: { accept: 'many', reject: 3 },
        positions: { spd: { up: 2 }, afd: null },
      }),
    ).toEqual({
      vote: { accept: 0, reject: 3 },
      positions: { spd: { up: 2, down: 0 }, afd: { up: 0, down: 0 } },
    });
    expect(
      toFeedOpinion({ vote: 'maybe', positions: { spd: 'up', afd: 'meh' } }),
    ).toEqual({ vote: null, positions: { spd: 'up' } });
  });
});

describe('publishedCounts', () => {
  const k = MIN_PUBLISHED_ANSWERS;

  it('withholds a vote with fewer answers than the minimum', () => {
    const counts = toOpinionCounts({ vote: { accept: k - 2, reject: 1 } });
    expect(publishedCounts(counts).vote).toBeNull();
  });

  it('shows a vote once it reaches the minimum', () => {
    const counts = toOpinionCounts({ vote: { accept: k - 1, reject: 1 } });
    expect(publishedCounts(counts).vote).toEqual({ accept: k - 1, reject: 1 });
  });

  it('withholds each position on its own', () => {
    const counts = toOpinionCounts({
      positions: { gruene: { up: k, down: 3 }, spd: { up: 1, down: 0 } },
    });
    expect(publishedCounts(counts).positions).toEqual({
      gruene: { up: k, down: 3 },
    });
  });

  it('round-trips through a response', () => {
    const counts = publishedCounts(
      toOpinionCounts({
        vote: { accept: 1, reject: 0 },
        positions: { gruene: { up: k, down: 0 } },
      }),
    );
    expect(toPublishedCounts(JSON.parse(JSON.stringify(counts)))).toEqual(
      counts,
    );
    expect(toPublishedCounts(undefined)).toEqual({ vote: null, positions: {} });
  });
});

describe('scoreOf', () => {
  it('is agreement minus disagreement', () => {
    const counts = publishedCounts(
      toOpinionCounts({ positions: { gruene: { up: 3, down: 10 } } }),
    );
    expect(scoreOf(counts, 'gruene')).toBe(-7);
  });

  it('is null for a withheld position', () => {
    expect(scoreOf({ vote: null, positions: {} }, 'spd')).toBeNull();
  });
});

describe('isEmptyOpinion', () => {
  it('is true only without a vote and positions', () => {
    expect(isEmptyOpinion(EMPTY_OPINION)).toBe(true);
    expect(isEmptyOpinion({ vote: 'accept', positions: {} })).toBe(false);
    expect(isEmptyOpinion({ vote: null, positions: { spd: 'up' } })).toBe(
      false,
    );
  });
});

describe('isAbandoned', () => {
  const cutoff = Date.UTC(2026, 4, 1);

  it('is true for a uid that no longer exists', () => {
    expect(isAbandoned(null, cutoff)).toBe(true);
  });

  it('is true for an anonymous reader not seen since the cutoff', () => {
    expect(
      isAbandoned({ anonymous: true, lastActiveMs: cutoff - 1 }, cutoff),
    ).toBe(true);
  });

  it('keeps an anonymous reader seen since the cutoff', () => {
    expect(isAbandoned({ anonymous: true, lastActiveMs: cutoff }, cutoff)).toBe(
      false,
    );
  });

  it('keeps an account holder, who can still sign in and withdraw', () => {
    expect(isAbandoned({ anonymous: false, lastActiveMs: 0 }, cutoff)).toBe(
      false,
    );
  });
});

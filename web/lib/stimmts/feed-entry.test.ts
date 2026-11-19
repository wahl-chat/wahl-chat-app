import { describe, expect, it } from 'bun:test';
import { PUZZLES } from './content';
import { NEW_FOR_DAYS, feedEntry, recordFeedVisit } from './feed-entry';
import { EMPTY_PROGRESS, type Progress } from './progress';
import { type StimmtsStatus, readStimmtsStatus } from './status';

const on: StimmtsStatus = { enabled: true, launchDate: '2026-11-15' };
const found = PUZZLES.find((puzzle) => puzzle.id === 'tankrabatt-2026');
if (!found) {
  throw new Error('fixture puzzle missing');
}
const first = found;

/** A finished game of the first puzzle with `right` correct answers. */
function finished(finishedOn: string, right: number): Progress {
  const guesses = Object.fromEntries(
    first.parties.map((party, index) => [
      party.partyId,
      index < right ? party.answer : party.answer === 'yes' ? 'no' : 'yes',
    ]),
  );
  return {
    ...EMPTY_PROGRESS,
    games: { [first.id]: { guesses, finishedOn, cast: false } },
  } as Progress;
}

const day1 = new Date('2026-11-15T22:59:59Z');

describe('feedEntry', () => {
  it('is hidden when off, before launch and after the last puzzle', () => {
    const base = { now: day1, progress: EMPTY_PROGRESS, visitDays: 1 };
    expect(feedEntry({ ...base, status: { enabled: false } }).kind).toBe(
      'hidden',
    );
    expect(
      feedEntry({
        ...base,
        status: { enabled: true, launchDate: '2026-11-16' },
      }).kind,
    ).toBe('hidden');
    const past = new Date('2030-01-01T12:00:00Z');
    expect(feedEntry({ ...base, status: on, now: past }).kind).toBe('hidden');
  });

  it('offers day 1 until Berlin midnight, then day 2', () => {
    const base = { status: on, progress: EMPTY_PROGRESS, visitDays: 1 };
    const one = feedEntry({ ...base, now: day1 });
    expect(one).toMatchObject({
      kind: 'play',
      number: 1,
      shortName: 'Der Tankrabatt',
    });
    if (one.kind === 'play') {
      expect(one.endsAt.toISOString()).toBe('2026-11-15T23:00:00.000Z');
    }
    const two = feedEntry({ ...base, now: new Date('2026-11-15T23:00:01Z') });
    expect(two).toMatchObject({ kind: 'play', number: 2 });
    expect(two.kind === 'play' && two.shortName).toBe(PUZZLES[1].shortName);
  });

  it('offers play the day after finishing and played on the day', () => {
    const now = new Date('2026-11-15T10:00:00Z');
    const play = feedEntry({
      status: on,
      now,
      progress: finished('2026-11-14', 3),
      visitDays: 1,
    });
    expect(play.kind).toBe('play');
    expect(
      feedEntry({
        status: on,
        now,
        progress: finished('2026-11-15', 3),
        visitDays: 1,
      }),
    ).toEqual({ kind: 'played', number: 1, score: 3 });
  });

  it('is new for 14 days and while under 3 visit days', () => {
    const isNew = (day: number, visitDays: number) => {
      const entry = feedEntry({
        status: on,
        now: new Date(Date.UTC(2026, 10, 14 + day, 12)),
        progress: EMPTY_PROGRESS,
        visitDays,
      });
      return entry.kind === 'play' && entry.isNew;
    };
    expect(isNew(NEW_FOR_DAYS, 2)).toBe(true);
    expect(isNew(NEW_FOR_DAYS + 1, 2)).toBe(false);
    expect(isNew(1, 3)).toBe(false);
  });
});

describe('readStimmtsStatus', () => {
  it('is off when the read throws', async () => {
    const status = await readStimmtsStatus(async () => {
      throw new Error('unavailable');
    });
    expect(status).toEqual({ enabled: false });
  });

  it('parses the doc otherwise', async () => {
    const status = await readStimmtsStatus(async () => ({
      enabled: true,
      launch_date: '2026-11-15',
    }));
    expect(status).toEqual(on);
  });
});

describe('recordFeedVisit', () => {
  function fake(initial?: string) {
    const data = new Map<string, string>();
    if (initial !== undefined) {
      data.set('stimmts:feed-visits', initial);
    }
    return {
      getItem: (key: string) => data.get(key) ?? null,
      setItem: (key: string, value: string) => void data.set(key, value),
    };
  }

  it('counts once per day', () => {
    const storage = fake();
    expect(recordFeedVisit(storage, '2026-11-15')).toBe(1);
    expect(recordFeedVisit(storage, '2026-11-15')).toBe(1);
    expect(recordFeedVisit(storage, '2026-11-16')).toBe(2);
  });

  it('survives missing storage and junk', () => {
    expect(recordFeedVisit(null, '2026-11-15')).toBe(1);
    expect(recordFeedVisit(fake('{nope'), '2026-11-15')).toBe(1);
    expect(recordFeedVisit(fake('{"last":5,"count":"x"}'), '2026-11-15')).toBe(
      1,
    );
  });
});

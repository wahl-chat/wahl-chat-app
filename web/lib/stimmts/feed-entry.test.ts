import { describe, expect, it } from 'bun:test';
import { PUZZLES } from './content';
import {
  type FeedEntry,
  feedCardLabel,
  feedEntry,
  hasPuzzleToday,
  nextFeedTick,
  remainingLabel,
} from './feed-entry';
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
    const base = { now: day1, progress: EMPTY_PROGRESS };
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
    const base = { status: on, progress: EMPTY_PROGRESS };
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
    });
    expect(play.kind).toBe('play');
    expect(
      feedEntry({
        status: on,
        now,
        progress: finished('2026-11-15', 3),
      }),
    ).toEqual({ kind: 'played', number: 1, score: 3 });
  });
});

describe('readStimmtsStatus', () => {
  it('is off and reports the error when the read throws', async () => {
    const reported: unknown[] = [];
    const failure = new Error('unavailable');
    const status = await readStimmtsStatus(
      async () => {
        throw failure;
      },
      (error) => reported.push(error),
    );
    expect(status).toEqual({ enabled: false });
    expect(reported).toEqual([failure]);
  });

  it('passes the read through otherwise', async () => {
    const reported: unknown[] = [];
    const status = await readStimmtsStatus(
      async () => on,
      (error) => reported.push(error),
    );
    expect(status).toEqual(on);
    expect(reported).toEqual([]);
  });
});

describe('remainingLabel', () => {
  const at = (h: number, m: number, s: number) =>
    ((h * 60 + m) * 60 + s) * 1000;

  it('speaks hours and whole minutes', () => {
    expect(remainingLabel(at(8, 41, 27))).toBe('8 Stunden 41 Minuten');
    expect(remainingLabel(at(1, 1, 0))).toBe('1 Stunde 1 Minute');
  });

  it('leaves out an empty part', () => {
    expect(remainingLabel(at(0, 12, 5))).toBe('12 Minuten');
    expect(remainingLabel(at(3, 0, 30))).toBe('3 Stunden');
  });

  it('says less than a minute at the very end, never zero', () => {
    expect(remainingLabel(at(0, 0, 59))).toBe('weniger als 1 Minute');
    expect(remainingLabel(-5000)).toBe('weniger als 1 Minute');
  });
});

describe('feedCardLabel', () => {
  // 15:18:33 in Berlin on launch day, 8:41:27 before the next puzzle.
  const now = new Date('2026-11-15T14:18:33Z');
  const play: FeedEntry = {
    kind: 'play',
    number: 1,
    shortName: 'Der Tankrabatt',
    endsAt: new Date('2026-11-15T23:00:00Z'),
  };

  it('reads the whole card as one link', () => {
    expect(feedCardLabel(play, now)).toBe(
      'Stimmt’s?: Heute: Der Tankrabatt. Jeden Tag ein neues Quiz. Noch 8 Stunden 41 Minuten. Los geht’s',
    );
  });

  it('has no label when there is nothing to play', () => {
    expect(feedCardLabel({ kind: 'hidden' }, now)).toBeNull();
    expect(
      feedCardLabel({ kind: 'played', number: 1, score: 4 }, now),
    ).toBeNull();
  });
});

describe('hasPuzzleToday', () => {
  it('is false while the switch is off', () => {
    expect(hasPuzzleToday({ enabled: false }, day1)).toBe(false);
  });

  it('is false on the eve of the launch', () => {
    expect(
      hasPuzzleToday(
        { enabled: true, launchDate: '2026-11-16' },
        new Date('2026-11-15T12:00:00Z'),
      ),
    ).toBe(false);
  });

  it('is true on day 1', () => {
    expect(hasPuzzleToday(on, new Date('2026-11-15T12:00:00Z'))).toBe(true);
  });

  it('is false once the last puzzle has run', () => {
    expect(hasPuzzleToday(on, new Date('2030-01-01T12:00:00Z'))).toBe(false);
  });
});

describe('nextFeedTick', () => {
  it('ticks every second while there is a countdown', () => {
    expect(nextFeedTick('play', new Date('2026-11-15T14:18:33Z'))).toBe(1000);
  });

  it('otherwise wakes just after the next Berlin midnight', () => {
    // 22:59:00 UTC is 23:59:00 in Berlin: one minute, plus the margin.
    const now = new Date('2026-11-15T22:59:00Z');
    expect(nextFeedTick('played', now)).toBe(61_000);
    expect(nextFeedTick('hidden', now)).toBe(61_000);
  });
});

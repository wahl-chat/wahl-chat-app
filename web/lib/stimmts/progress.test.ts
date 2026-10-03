import { describe, expect, it } from 'bun:test';
import { PUZZLES } from './content';
import {
  EMPTY_PROGRESS,
  type Progress,
  getGame,
  parseProgress,
  recordAnswer,
  removeGame,
} from './progress';
import type { VoteAnswer } from './types';

const [first, second] = PUZZLES;
// Seating order: linke, spd, gruene, cdu, afd.
const PARTIES = ['linke', 'spd', 'gruene', 'cdu', 'afd'];

function answerAll(
  progress: Progress,
  puzzle: (typeof PUZZLES)[number],
  today: string,
  answer: VoteAnswer = 'yes',
): Progress {
  return PARTIES.reduce(
    (state, partyId) => recordAnswer(state, puzzle, partyId, answer, today),
    progress,
  );
}

describe('recordAnswer', () => {
  it('saves an answer and leaves the game open until the last party', () => {
    let progress = recordAnswer(
      EMPTY_PROGRESS,
      first,
      'linke',
      'no',
      '2026-11-01',
    );
    progress = recordAnswer(progress, first, 'spd', 'yes', '2026-11-01');
    expect(getGame(progress, first.id)).toEqual({
      guesses: { linke: 'no', spd: 'yes' },
      finishedOn: null,
    });
    expect(progress.streak.current).toBe(0);
  });

  it('finishes with the last answer and counts the day for the streak', () => {
    const progress = answerAll(EMPTY_PROGRESS, first, '2026-11-01');
    expect(getGame(progress, first.id).finishedOn).toBe('2026-11-01');
    expect(progress.streak).toEqual({
      current: 1,
      best: 1,
      lastPlayed: '2026-11-01',
    });
  });

  it('treats answers as final', () => {
    const once = recordAnswer(
      EMPTY_PROGRESS,
      first,
      'linke',
      'no',
      '2026-11-01',
    );
    const again = recordAnswer(once, first, 'linke', 'yes', '2026-11-01');
    expect(again).toBe(once);
    expect(getGame(again, first.id).guesses.linke).toBe('no');
  });

  it('ignores a party that is not in the puzzle', () => {
    const progress = recordAnswer(
      EMPTY_PROGRESS,
      first,
      'fdp',
      'yes',
      '2026-11-01',
    );
    expect(progress).toBe(EMPTY_PROGRESS);
  });

  it('ignores answers once the game is finished', () => {
    const finished = answerAll(EMPTY_PROGRESS, first, '2026-11-01', 'no');
    const after = recordAnswer(finished, first, 'afd', 'yes', '2026-11-02');
    expect(after).toBe(finished);
  });

  it('keeps puzzles apart and does not mutate the previous state', () => {
    const afterFirst = recordAnswer(
      EMPTY_PROGRESS,
      first,
      'linke',
      'no',
      '2026-11-01',
    );
    const afterSecond = recordAnswer(
      afterFirst,
      second,
      'linke',
      'yes',
      '2026-11-01',
    );
    expect(getGame(afterSecond, first.id).guesses).toEqual({ linke: 'no' });
    expect(getGame(afterSecond, second.id).guesses).toEqual({ linke: 'yes' });
    expect(getGame(afterFirst, second.id).guesses).toEqual({});
    expect(EMPTY_PROGRESS.games).toEqual({});
  });

  it('extends the streak across days but counts a day only once', () => {
    let progress = answerAll(EMPTY_PROGRESS, first, '2026-11-01');
    progress = answerAll(progress, second, '2026-11-02');
    expect(progress.streak.current).toBe(2);

    const sameDay = answerAll(progress, PUZZLES[2], '2026-11-02');
    expect(sameDay.streak.current).toBe(2);
  });
});

describe('parseProgress', () => {
  it('round-trips what recordAnswer produces', () => {
    const progress = answerAll(EMPTY_PROGRESS, first, '2026-11-01');
    expect(parseProgress(JSON.parse(JSON.stringify(progress)))).toEqual(
      progress,
    );
  });

  it('falls back to an empty state for anything unrecognisable', () => {
    for (const raw of [null, undefined, 'text', 42, [], {}, { version: 99 }]) {
      expect(parseProgress(raw)).toEqual(EMPTY_PROGRESS);
    }
  });

  it('keeps the readable games and drops the damaged ones', () => {
    const progress = parseProgress({
      version: 1,
      games: {
        good: { guesses: { linke: 'no' }, finishedOn: null },
        badAnswer: { guesses: { linke: 'maybe' }, finishedOn: null },
        badDate: { guesses: {}, finishedOn: '2026-02-31' },
        notAnObject: 7,
      },
      streak: { current: 2, best: 3, lastPlayed: '2026-11-02' },
    });
    expect(Object.keys(progress.games)).toEqual(['good']);
    expect(progress.streak).toEqual({
      current: 2,
      best: 3,
      lastPlayed: '2026-11-02',
    });
  });

  it('resets only the streak when just the streak is damaged', () => {
    const progress = parseProgress({
      version: 1,
      games: { good: { guesses: {}, finishedOn: null } },
      streak: { current: 'many', best: 1, lastPlayed: null },
    });
    expect(Object.keys(progress.games)).toEqual(['good']);
    expect(progress.streak).toEqual({ current: 0, best: 0, lastPlayed: null });
  });
});

describe('removeGame', () => {
  it('forgets one puzzle and keeps the other puzzles and the streak', () => {
    let progress = answerAll(EMPTY_PROGRESS, first, '2026-11-01');
    progress = answerAll(progress, second, '2026-11-02');

    const after = removeGame(progress, second.id);
    expect(getGame(after, second.id)).toEqual({
      guesses: {},
      finishedOn: null,
    });
    expect(getGame(after, first.id).finishedOn).toBe('2026-11-01');
    expect(after.streak).toEqual(progress.streak);
    expect(progress.games[second.id]).toBeDefined(); // the old state is untouched
  });

  it('lets a puzzle be replayed without counting its day twice', () => {
    let progress = answerAll(EMPTY_PROGRESS, first, '2026-11-01');
    progress = answerAll(progress, second, '2026-11-02');
    expect(progress.streak.current).toBe(2);

    progress = removeGame(progress, second.id);
    progress = answerAll(progress, second, '2026-11-02');
    expect(progress.streak.current).toBe(2);
  });

  it('returns the same object for a puzzle that was never played', () => {
    expect(removeGame(EMPTY_PROGRESS, first.id)).toBe(EMPTY_PROGRESS);
  });
});

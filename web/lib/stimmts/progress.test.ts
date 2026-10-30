import { describe, expect, it } from 'bun:test';
import { FIXTURE_PUZZLES as PUZZLES } from './fixtures';
import {
  EMPTY_PROGRESS,
  type Progress,
  castCard,
  getGame,
  mergeProgress,
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
      cast: false,
    });
  });

  it('finishes with the last answer, the card still in hand', () => {
    const progress = answerAll(EMPTY_PROGRESS, first, '2026-11-01');
    expect(getGame(progress, first.id).finishedOn).toBe('2026-11-01');
    expect(getGame(progress, first.id).cast).toBe(false);
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
});

describe('castCard', () => {
  it('casts the card of a finished game, once', () => {
    const finished = answerAll(EMPTY_PROGRESS, first, '2026-11-01');
    const cast = castCard(finished, first.id);
    expect(getGame(cast, first.id).cast).toBe(true);
    expect(getGame(finished, first.id).cast).toBe(false); // not mutated
    expect(castCard(cast, first.id)).toBe(cast);
  });

  it('has no card to cast while the game is open', () => {
    const open = recordAnswer(
      EMPTY_PROGRESS,
      first,
      'linke',
      'no',
      '2026-11-01',
    );
    expect(castCard(open, first.id)).toBe(open);
    expect(castCard(EMPTY_PROGRESS, first.id)).toBe(EMPTY_PROGRESS);
  });
});

describe('parseProgress', () => {
  it('round-trips what recordAnswer and castCard produce', () => {
    const progress = castCard(
      answerAll(EMPTY_PROGRESS, first, '2026-11-01'),
      first.id,
    );
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
    });
    expect(Object.keys(progress.games)).toEqual(['good']);
  });

  it('reads saves from before the Stimmkarte, with no cast flag', () => {
    const progress = parseProgress({
      version: 1,
      games: { old: { guesses: { linke: 'no' }, finishedOn: '2026-11-01' } },
      streak: { current: 1, best: 1, lastPlayed: '2026-11-01' },
    });
    expect(progress).toEqual({
      version: 1,
      games: {
        old: {
          guesses: { linke: 'no' },
          finishedOn: '2026-11-01',
          cast: false,
        },
      },
    });
  });

  it('never treats an open game as cast', () => {
    const progress = parseProgress({
      version: 1,
      games: { open: { guesses: {}, finishedOn: null, cast: true } },
    });
    expect(getGame(progress, 'open').cast).toBe(false);
  });
});

describe('removeGame', () => {
  it('forgets one puzzle and keeps the other puzzles', () => {
    let progress = answerAll(EMPTY_PROGRESS, first, '2026-11-01');
    progress = answerAll(progress, second, '2026-11-02');

    const after = removeGame(progress, second.id);
    expect(getGame(after, second.id)).toEqual({
      guesses: {},
      finishedOn: null,
      cast: false,
    });
    expect(getGame(after, first.id).finishedOn).toBe('2026-11-01');
    expect(progress.games[second.id]).toBeDefined(); // the old state is untouched
  });

  it('returns the same object for a puzzle that was never played', () => {
    expect(removeGame(EMPTY_PROGRESS, first.id)).toBe(EMPTY_PROGRESS);
  });
});

describe('mergeProgress', () => {
  it('lets the saved copy win for every game it holds', () => {
    const saved = answerAll(EMPTY_PROGRESS, first, '2026-11-01', 'no');
    const stale = recordAnswer(
      EMPTY_PROGRESS,
      first,
      'linke',
      'yes',
      '2026-11-01',
    );
    expect(mergeProgress(saved, stale)).toBe(saved);
  });

  it('keeps games only this page knows about', () => {
    const saved = answerAll(EMPTY_PROGRESS, first, '2026-11-01');
    const current = recordAnswer(
      EMPTY_PROGRESS,
      second,
      'linke',
      'no',
      '2026-11-02',
    );
    const merged = mergeProgress(saved, current);
    expect(getGame(merged, first.id).finishedOn).toBe('2026-11-01');
    expect(getGame(merged, second.id).guesses).toEqual({ linke: 'no' });
  });
});

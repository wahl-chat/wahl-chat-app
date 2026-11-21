import { describe, expect, it } from 'bun:test';
import { FIXTURE_PUZZLES as PUZZLES } from './fixtures';
import {
  EMPTY_PROGRESS,
  type Progress,
  castCard,
  finishGame,
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

/** Every party answered, then "Auflösen". */
function playAll(
  progress: Progress,
  puzzle: (typeof PUZZLES)[number],
  today: string,
  answer: VoteAnswer = 'yes',
): Progress {
  return finishGame(answerAll(progress, puzzle, today, answer), puzzle, today);
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

  it('changes a guess while the game is open', () => {
    const once = recordAnswer(
      EMPTY_PROGRESS,
      first,
      'linke',
      'no',
      '2026-11-01',
    );
    const changed = recordAnswer(once, first, 'linke', 'yes', '2026-11-01');
    expect(getGame(changed, first.id).guesses.linke).toBe('yes');
    expect(getGame(once, first.id).guesses.linke).toBe('no'); // not mutated
    // The same answer again is no change at all.
    expect(recordAnswer(changed, first, 'linke', 'yes', '2026-11-01')).toBe(
      changed,
    );
  });

  it('the fifth guess does not finish the game', () => {
    const progress = answerAll(EMPTY_PROGRESS, first, '2026-11-01');
    expect(getGame(progress, first.id).finishedOn).toBeNull();
    expect(Object.keys(getGame(progress, first.id).guesses)).toHaveLength(5);
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
    const finished = playAll(EMPTY_PROGRESS, first, '2026-11-01', 'no');
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

describe('finishGame', () => {
  it('finishGame finishes a complete game on today', () => {
    const complete = answerAll(EMPTY_PROGRESS, first, '2026-11-01');
    const finished = finishGame(complete, first, '2026-11-02');
    expect(getGame(finished, first.id)).toEqual({
      guesses: getGame(complete, first.id).guesses,
      finishedOn: '2026-11-02',
      cast: false,
    });
    expect(getGame(complete, first.id).finishedOn).toBeNull(); // not mutated
    expect(finishGame(finished, first, '2026-11-03')).toBe(finished);
  });

  it('finishGame leaves an incomplete game alone (same object)', () => {
    const open = recordAnswer(
      EMPTY_PROGRESS,
      first,
      'linke',
      'no',
      '2026-11-01',
    );
    expect(finishGame(open, first, '2026-11-01')).toBe(open);
    expect(finishGame(EMPTY_PROGRESS, first, '2026-11-01')).toBe(
      EMPTY_PROGRESS,
    );
  });

  it('no guess changes after finishGame (same object)', () => {
    const finished = playAll(EMPTY_PROGRESS, first, '2026-11-01', 'no');
    for (const partyId of PARTIES) {
      expect(recordAnswer(finished, first, partyId, 'yes', '2026-11-01')).toBe(
        finished,
      );
    }
  });
});

describe('castCard', () => {
  it('casts the card of a finished game, once', () => {
    const finished = playAll(EMPTY_PROGRESS, first, '2026-11-01');
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
      playAll(EMPTY_PROGRESS, first, '2026-11-01'),
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

  it('reads a game without a cast flag as not cast, ignoring unknown keys', () => {
    const progress = parseProgress({
      version: 1,
      games: { old: { guesses: { linke: 'no' }, finishedOn: '2026-11-01' } },
      somethingElse: true,
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

  it('a save with 3 guesses and finishedOn null still parses and resumes', () => {
    const progress = parseProgress({
      version: 1,
      games: {
        [first.id]: {
          guesses: { linke: 'no', spd: 'yes', gruene: 'abstain' },
          finishedOn: null,
          cast: false,
        },
      },
    });
    expect(getGame(progress, first.id).guesses).toEqual({
      linke: 'no',
      spd: 'yes',
      gruene: 'abstain',
    });
    // The open guesses can still be changed, and the rest added and revealed.
    const changed = recordAnswer(progress, first, 'linke', 'yes', '2026-11-01');
    expect(getGame(changed, first.id).guesses.linke).toBe('yes');
    let resumed = recordAnswer(changed, first, 'cdu', 'yes', '2026-11-01');
    resumed = recordAnswer(resumed, first, 'afd', 'no', '2026-11-01');
    expect(
      getGame(finishGame(resumed, first, '2026-11-01'), first.id).finishedOn,
    ).toBe('2026-11-01');
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
    let progress = playAll(EMPTY_PROGRESS, first, '2026-11-01');
    progress = playAll(progress, second, '2026-11-02');

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
    const saved = playAll(EMPTY_PROGRESS, first, '2026-11-01', 'no');
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
    const saved = playAll(EMPTY_PROGRESS, first, '2026-11-01');
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

  it('mergeProgress keeps a finished game over an unfinished one with different guesses', () => {
    // This page revealed the game, but the save of that failed and storage
    // still holds the open game, with a guess changed since.
    const open = answerAll(EMPTY_PROGRESS, first, '2026-11-01', 'no');
    const savedOpen = recordAnswer(open, first, 'linke', 'yes', '2026-11-01');
    const revealed = finishGame(open, first, '2026-11-01');

    const merged = mergeProgress(savedOpen, revealed);
    expect(getGame(merged, first.id)).toEqual(getGame(revealed, first.id));
    // And the other way round, the saved finished game wins as before.
    expect(mergeProgress(revealed, savedOpen)).toBe(revealed);
  });
});

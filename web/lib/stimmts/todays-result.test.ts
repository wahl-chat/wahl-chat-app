import { describe, expect, it } from 'bun:test';
import { PUZZLES } from './content';
import { EMPTY_PROGRESS, type Progress } from './progress';
import { todaysResult } from './todays-result';

const puzzle = PUZZLES[0];

function finishedOn(date: string | null, right: number): Progress {
  const guesses = Object.fromEntries(
    puzzle.parties.map((party, index) => [
      party.partyId,
      index < right ? party.answer : party.answer === 'yes' ? 'no' : 'yes',
    ]),
  );
  return {
    ...EMPTY_PROGRESS,
    games: { [puzzle.id]: { guesses, finishedOn: date, cast: false } },
  } as Progress;
}

describe('todaysResult', () => {
  it('is null without a game finished today', () => {
    expect(todaysResult(EMPTY_PROGRESS, '2026-11-15')).toBeNull();
    expect(todaysResult(finishedOn(null, 3), '2026-11-15')).toBeNull();
    expect(todaysResult(finishedOn('2026-11-14', 3), '2026-11-15')).toBeNull();
  });

  it('scores the game finished today, party by party in seating order', () => {
    expect(todaysResult(finishedOn('2026-11-15', 3), '2026-11-15')).toEqual({
      correct: 3,
      total: puzzle.parties.length,
      verdicts: puzzle.parties.map((_, index) => index < 3),
    });
  });

  it('ignores a saved game whose puzzle no longer exists', () => {
    const progress = {
      ...EMPTY_PROGRESS,
      games: { gone: { guesses: {}, finishedOn: '2026-11-15', cast: false } },
    } as Progress;
    expect(todaysResult(progress, '2026-11-15')).toBeNull();
  });
});

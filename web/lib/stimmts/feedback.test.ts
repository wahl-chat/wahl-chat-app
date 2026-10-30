import { describe, expect, it } from 'bun:test';
import { shouldAskForFeedback } from './feedback';
import { EMPTY_PROGRESS, type Progress } from './progress';

function withGames(finished: number, open = 0): Progress {
  const games: Progress['games'] = {};
  for (let i = 0; i < finished; i++) {
    games[`done-${i}`] = { guesses: {}, finishedOn: '2026-11-01', cast: true };
  }
  for (let i = 0; i < open; i++) {
    games[`open-${i}`] = { guesses: {}, finishedOn: null, cast: false };
  }
  return { ...EMPTY_PROGRESS, games };
}

describe('shouldAskForFeedback', () => {
  it('asks once five puzzles are finished', () => {
    expect(shouldAskForFeedback(withGames(4), false)).toBe(false);
    expect(shouldAskForFeedback(withGames(5), false)).toBe(true);
    expect(shouldAskForFeedback(withGames(12), false)).toBe(true);
  });

  it('does not count puzzles left unfinished', () => {
    expect(shouldAskForFeedback(withGames(4, 3), false)).toBe(false);
  });

  it('never asks twice', () => {
    expect(shouldAskForFeedback(withGames(5), true)).toBe(false);
  });
});

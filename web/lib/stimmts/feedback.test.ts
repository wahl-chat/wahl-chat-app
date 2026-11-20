import { describe, expect, it } from 'bun:test';
import {
  markAsked,
  shouldAskForFeedback,
  shouldShowFeedCard,
  wasAsked,
} from './feedback';
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
  it('asks once the first puzzle is finished', () => {
    expect(shouldAskForFeedback(withGames(0), false)).toBe(false);
    expect(shouldAskForFeedback(withGames(1), false)).toBe(true);
    expect(shouldAskForFeedback(withGames(7), false)).toBe(true);
  });

  it('does not count puzzles left unfinished', () => {
    expect(shouldAskForFeedback(withGames(0, 3), false)).toBe(false);
  });

  it('never asks twice', () => {
    expect(shouldAskForFeedback(withGames(1), true)).toBe(false);
    expect(shouldAskForFeedback(withGames(5), true)).toBe(false);
  });
});

describe('shouldShowFeedCard', () => {
  const base = {
    progress: withGames(1),
    asked: false,
    studyRunning: false as boolean | null,
    flyingIn: false,
    gameOn: true as boolean | null,
  };

  it('shows after one finished game when the study is known off', () => {
    expect(shouldShowFeedCard(base)).toBe(true);
  });

  it('hidden while the study status is unknown (null)', () => {
    expect(shouldShowFeedCard({ ...base, studyRunning: null })).toBe(false);
  });

  it('hidden while the study runs', () => {
    expect(shouldShowFeedCard({ ...base, studyRunning: true })).toBe(false);
  });

  it('hidden while the game is switched off', () => {
    expect(shouldShowFeedCard({ ...base, gameOn: false })).toBe(false);
  });

  it('hidden while the game status is unknown (null)', () => {
    expect(shouldShowFeedCard({ ...base, gameOn: null })).toBe(false);
  });

  it('hidden on the fly-in visit', () => {
    expect(shouldShowFeedCard({ ...base, flyingIn: true })).toBe(false);
  });

  it('hidden once asked', () => {
    expect(shouldShowFeedCard({ ...base, asked: true })).toBe(false);
  });

  it('hidden before any game is finished', () => {
    expect(shouldShowFeedCard({ ...base, progress: withGames(0, 1) })).toBe(
      false,
    );
  });
});

describe('wasAsked', () => {
  it('survives a storage that throws', () => {
    const broken = {
      getItem() {
        throw new Error('blocked');
      },
      setItem() {
        throw new Error('blocked');
      },
    };
    expect(() => markAsked(broken)).not.toThrow();
    expect(wasAsked(broken)).toBe(true);
  });
});

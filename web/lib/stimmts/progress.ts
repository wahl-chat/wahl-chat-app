import { isIsoDate } from './berlin-time';
import { isComplete } from './score';
import { EMPTY_STREAK, type StreakState, recordPlay } from './streak';
import type { Guesses, Puzzle, VoteAnswer } from './types';
import { isVoteAnswer } from './validate';

/** Bumped when the saved shape changes; older saves are then discarded. */
export const PROGRESS_VERSION = 1;

export type GameProgress = {
  guesses: Guesses;
  /** Berlin date the last answer was given; null while the game is open. */
  finishedOn: string | null;
};

/** Everything saved on the player's device. */
export type Progress = {
  version: typeof PROGRESS_VERSION;
  /** By puzzle id, so earlier puzzles stay available for an archive later. */
  games: Record<string, GameProgress>;
  streak: StreakState;
};

export const EMPTY_PROGRESS: Progress = {
  version: PROGRESS_VERSION,
  games: {},
  streak: EMPTY_STREAK,
};

const NEW_GAME: GameProgress = { guesses: {}, finishedOn: null };

export function getGame(progress: Progress, puzzleId: string): GameProgress {
  return progress.games[puzzleId] ?? NEW_GAME;
}

/**
 * Records one answer. Answers are final: once a party has been answered, or
 * the game is finished, nothing changes, so reloading the page cannot be used
 * to take an answer back. Returns the same object when nothing changed.
 *
 * Giving the last answer finishes the game and counts the day for the streak.
 */
export function recordAnswer(
  progress: Progress,
  puzzle: Puzzle,
  partyId: string,
  answer: VoteAnswer,
  today: string,
): Progress {
  const game = getGame(progress, puzzle.id);
  const inPuzzle = puzzle.parties.some((party) => party.partyId === partyId);
  if (
    !inPuzzle ||
    game.finishedOn !== null ||
    game.guesses[partyId] !== undefined
  ) {
    return progress;
  }

  const guesses = { ...game.guesses, [partyId]: answer };
  const finished = isComplete(puzzle, guesses);
  return {
    ...progress,
    games: {
      ...progress.games,
      [puzzle.id]: { guesses, finishedOn: finished ? today : null },
    },
    streak: finished ? recordPlay(progress.streak, today) : progress.streak,
  };
}

/**
 * Forgets one puzzle's answers and keeps everything else, the streak included.
 * Only the preview mode uses it, to replay a puzzle without losing the days
 * played before it. Replaying the same day cannot count twice, because the
 * streak already holds that day.
 */
export function removeGame(progress: Progress, puzzleId: string): Progress {
  if (!(puzzleId in progress.games)) {
    return progress;
  }
  return {
    ...progress,
    games: Object.fromEntries(
      Object.entries(progress.games).filter(([id]) => id !== puzzleId),
    ),
  };
}

// Saved data comes from the browser's storage, where it can be stale, hand
// edited or corrupt. Be strict about its shape, but forgiving about losing it:
// anything unreadable is dropped instead of breaking the game.

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function parseGuesses(raw: unknown): Guesses | null {
  if (!isRecord(raw)) {
    return null;
  }
  const guesses: Guesses = {};
  for (const [partyId, answer] of Object.entries(raw)) {
    if (typeof answer !== 'string' || !isVoteAnswer(answer)) {
      return null;
    }
    guesses[partyId] = answer;
  }
  return guesses;
}

function parseGame(raw: unknown): GameProgress | null {
  if (!isRecord(raw)) {
    return null;
  }
  const guesses = parseGuesses(raw.guesses);
  const finishedOn = raw.finishedOn;
  if (!guesses || !(finishedOn === null || isIsoDate(finishedOn))) {
    return null;
  }
  return { guesses, finishedOn };
}

function parseStreak(raw: unknown): StreakState {
  if (
    !isRecord(raw) ||
    !Number.isInteger(raw.current) ||
    !Number.isInteger(raw.best) ||
    !(raw.lastPlayed === null || isIsoDate(raw.lastPlayed))
  ) {
    return EMPTY_STREAK;
  }
  return {
    current: raw.current as number,
    best: raw.best as number,
    lastPlayed: raw.lastPlayed,
  };
}

export function parseProgress(raw: unknown): Progress {
  if (!isRecord(raw) || raw.version !== PROGRESS_VERSION) {
    return EMPTY_PROGRESS;
  }
  const games: Record<string, GameProgress> = {};
  if (isRecord(raw.games)) {
    for (const [puzzleId, rawGame] of Object.entries(raw.games)) {
      const game = parseGame(rawGame);
      if (game) {
        games[puzzleId] = game;
      }
    }
  }
  return {
    version: PROGRESS_VERSION,
    games,
    streak: parseStreak(raw.streak),
  };
}

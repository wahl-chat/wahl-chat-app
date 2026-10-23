import { isIsoDate } from './berlin-time';
import { isComplete } from './score';
import type { Guesses, Puzzle, VoteAnswer } from './types';
import { isVoteAnswer } from './validate';

/** Bumped when the saved shape changes; older saves are then discarded. */
export const PROGRESS_VERSION = 1;

export type GameProgress = {
  guesses: Guesses;
  /** Berlin date the last answer was given; null while the game is open. */
  finishedOn: string | null;
  /**
   * True once the player has cast the day's Stimmkarte into the urn. A reload
   * then opens on the Wahlperiode and the countdown instead of the card.
   */
  cast: boolean;
};

/**
 * Everything saved on the player's device. The streak and the Wahlperiode are
 * worked out from the finished games (see period.ts), so they can never
 * disagree with the seats the player sees.
 */
export type Progress = {
  version: typeof PROGRESS_VERSION;
  /** By puzzle id, so earlier puzzles stay available for an archive later. */
  games: Record<string, GameProgress>;
};

export const EMPTY_PROGRESS: Progress = {
  version: PROGRESS_VERSION,
  games: {},
};

const NEW_GAME: GameProgress = { guesses: {}, finishedOn: null, cast: false };

export function getGame(progress: Progress, puzzleId: string): GameProgress {
  return progress.games[puzzleId] ?? NEW_GAME;
}

/**
 * Records one answer. Answers are final: once a party has been answered, or
 * the game is finished, nothing changes, so reloading the page cannot be used
 * to take an answer back. Returns the same object when nothing changed.
 *
 * Giving the last answer finishes the game.
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
      [puzzle.id]: {
        guesses,
        finishedOn: finished ? today : null,
        cast: false,
      },
    },
  };
}

/**
 * Marks a finished game's Stimmkarte as cast. An open game has no card to
 * cast yet, and casting twice changes nothing; both return the same object.
 */
export function castCard(progress: Progress, puzzleId: string): Progress {
  const game = progress.games[puzzleId];
  if (!game || game.finishedOn === null || game.cast) {
    return progress;
  }
  return {
    ...progress,
    games: { ...progress.games, [puzzleId]: { ...game, cast: true } },
  };
}

/**
 * Forgets one puzzle's answers and keeps every other day. Only the preview
 * mode uses it, to replay a puzzle without losing the days played before it.
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
  // Saves from before the Stimmkarte have no flag: their card was never cast.
  const cast = raw.cast === true && finishedOn !== null;
  return { guesses, finishedOn, cast };
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
  // Older saves also carry a stored streak; it is derived from the games now,
  // so it is left behind on the next save.
  return { version: PROGRESS_VERSION, games };
}

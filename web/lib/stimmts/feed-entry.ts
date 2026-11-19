import { berlinDate, nextPuzzleAt } from './berlin-time';
import { PUZZLES, createSchedule } from './content';
import { type Progress, getGame } from './progress';
import type { StorageLike } from './progress-store';
import { getTodaysPuzzle } from './schedule';
import { scorePuzzle } from './score';
import type { StimmtsStatus } from './status';

export type FeedEntry =
  | { kind: 'hidden' }
  | {
      kind: 'play';
      number: number;
      shortName: string;
      endsAt: Date;
      isNew: boolean;
    }
  | { kind: 'played'; number: number; score: number };

/** The card counts as new for the first two weeks of the game... */
export const NEW_FOR_DAYS = 14;
/** ...or until the visitor has opened the feed on this many different days. */
export const NEW_FOR_VISITS = 3;

const VISITS_KEY = 'stimmts:feed-visits';

type Args = {
  status: StimmtsStatus;
  now: Date;
  progress: Progress;
  /** Berlin days on which this device opened the feed (see recordFeedVisit). */
  visitDays: number;
};

export function feedEntry({
  status,
  now,
  progress,
  visitDays,
}: Args): FeedEntry {
  if (!status.enabled) {
    return { kind: 'hidden' };
  }
  const today = getTodaysPuzzle({
    schedule: createSchedule(status.launchDate),
    puzzles: PUZZLES,
    now,
  });
  if (today.status !== 'active') {
    return { kind: 'hidden' };
  }
  const { number, puzzle } = today;
  const game = getGame(progress, puzzle.id);
  if (game.finishedOn === berlinDate(now)) {
    return {
      kind: 'played',
      number,
      score: scorePuzzle(puzzle, game.guesses).correct,
    };
  }
  return {
    kind: 'play',
    number,
    shortName: puzzle.shortName,
    endsAt: nextPuzzleAt(now),
    isNew: number <= NEW_FOR_DAYS && visitDays < NEW_FOR_VISITS,
  };
}

/**
 * Counts the Berlin days this device opened the feed, once per day, to tell
 * when the card stops being new. Storage that is missing, blocked or corrupt
 * simply counts this visit as the first.
 */
export function recordFeedVisit(
  storage: StorageLike | null,
  today: string,
): number {
  let last: string | null = null;
  let count = 0;
  try {
    const saved = JSON.parse(storage?.getItem(VISITS_KEY) ?? 'null');
    if (
      saved &&
      typeof saved.last === 'string' &&
      Number.isInteger(saved.count) &&
      saved.count > 0
    ) {
      last = saved.last;
      count = saved.count;
    }
  } catch {
    // Unreadable history is no history.
  }
  if (last === today) {
    return count;
  }
  count += 1;
  try {
    storage?.setItem(VISITS_KEY, JSON.stringify({ last: today, count }));
  } catch {
    // Blocked storage: the count just does not persist.
  }
  return count;
}

import { berlinDate, nextPuzzleAt } from './berlin-time';
import { PUZZLES, createSchedule } from './content';
import { EMPTY_PROGRESS, type Progress, getGame } from './progress';
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
 * Whether the switch is on and a puzzle runs today, whatever this device has
 * played. The server renders the feed card from this, so the card is not
 * drawn before the launch or after the last puzzle only to vanish on mount.
 */
export function hasPuzzleToday(status: StimmtsStatus, now: Date): boolean {
  return (
    feedEntry({ status, now, progress: EMPTY_PROGRESS, visitDays: 0 }).kind !==
    'hidden'
  );
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

function counted(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

/**
 * The countdown as a screen reader says it, "8 Stunden 41 Minuten". The
 * visible clock ticks every second, which is noise when read aloud, so the
 * spoken form stops at minutes. Seconds round up as on the clock, so both
 * always show the same hours and minutes.
 */
export function remainingLabel(milliseconds: number): string {
  const totalMinutes = Math.floor(
    Math.max(0, Math.ceil(milliseconds / 1000)) / 60,
  );
  if (totalMinutes === 0) {
    return 'weniger als 1 Minute';
  }
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return [
    hours > 0 ? counted(hours, 'Stunde', 'Stunden') : null,
    minutes > 0 ? counted(minutes, 'Minute', 'Minuten') : null,
  ]
    .filter(Boolean)
    .join(' ');
}

/**
 * The accessible name of the feed card, which is one link: everything the
 * card shows, in reading order. Null when there is no card to play.
 */
export function feedCardLabel(entry: FeedEntry, now: Date): string | null {
  if (entry.kind !== 'play') {
    return null;
  }
  const name = entry.isNew ? 'Stimmt’s?, neu' : 'Stimmt’s?';
  const remaining = remainingLabel(entry.endsAt.getTime() - now.getTime());
  return `${name}: Heute: ${entry.shortName}. Jeden Tag ein neues Quiz. Noch ${remaining}. Los geht’s`;
}

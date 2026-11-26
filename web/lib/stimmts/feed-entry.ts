import { berlinDate, nextPuzzleAt } from './berlin-time';
import { PUZZLES, createSchedule } from './content';
import { EMPTY_PROGRESS, type Progress, getGame } from './progress';
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
    }
  | { kind: 'played'; number: number; score: number };

type Args = {
  status: StimmtsStatus;
  now: Date;
  progress: Progress;
};

export function feedEntry({ status, now, progress }: Args): FeedEntry {
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
  };
}

/**
 * Whether the switch is on and a puzzle runs today, whatever this device has
 * played. The server renders the feed card from this, so the card is not
 * drawn before the launch or after the last puzzle only to vanish on mount.
 */
export function hasPuzzleToday(status: StimmtsStatus, now: Date): boolean {
  return feedEntry({ status, now, progress: EMPTY_PROGRESS }).kind !== 'hidden';
}

/** Past midnight by this much, so the wake-up lands safely on the new day. */
const ROLLOVER_MARGIN_MS = 1000;

/**
 * Milliseconds until an open feed should look at the clock again: every
 * second while the countdown runs, otherwise just after the next Berlin
 * midnight, when a played day turns into a new puzzle or the launch begins.
 */
export function nextFeedTick(kind: FeedEntry['kind'], now: Date): number {
  return kind === 'play'
    ? 1000
    : nextPuzzleAt(now).getTime() - now.getTime() + ROLLOVER_MARGIN_MS;
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
  const remaining = remainingLabel(entry.endsAt.getTime() - now.getTime());
  return `Stimmt’s?: Heute: ${entry.shortName}. Jeden Tag ein neues Quiz. Noch ${remaining}. Los geht’s`;
}

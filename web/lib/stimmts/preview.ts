import { addDays, berlinDate, daysBetween } from './berlin-time';
import type { Schedule } from './types';

/**
 * Preview mode lets us play any day's puzzle, drafts included, before the game
 * is live. It is on while developing and wherever
 * NEXT_PUBLIC_STIMMTS_PREVIEW=true (a test deployment); production leaves it
 * off, so players only ever get the real puzzle of the day.
 */
export function isPreviewEnabled(): boolean {
  return (
    process.env.NODE_ENV === 'development' ||
    process.env.NEXT_PUBLIC_STIMMTS_PREVIEW === 'true'
  );
}

export type Clock = {
  /** The moment the game treats as "now". */
  now: Date;
  allowDrafts: boolean;
};

type ClockOptions = {
  previewEnabled: boolean;
  /** The page's query string, e.g. "?day=3". */
  search: string;
  schedule: Schedule;
  now: Date;
};

/**
 * The clock the game runs on. Normally the real one; in preview mode `?day=N`
 * jumps to the N-th day of the schedule, and without it the game shows today's
 * puzzle (or day 1 before the start date, so there is always something to see).
 */
export function resolveClock({
  previewEnabled,
  search,
  schedule,
  now,
}: ClockOptions): Clock {
  if (!previewEnabled) {
    return { now, allowDrafts: false };
  }

  const requested = Number(new URLSearchParams(search).get('day'));
  const today = daysBetween(schedule.startDate, berlinDate(now)) + 1;
  const day =
    Number.isInteger(requested) && requested >= 1
      ? requested
      : Math.max(1, today);

  // Midday UTC is early afternoon in Berlin, safely inside that calendar day.
  return {
    now: new Date(`${addDays(schedule.startDate, day - 1)}T12:00:00Z`),
    allowDrafts: true,
  };
}

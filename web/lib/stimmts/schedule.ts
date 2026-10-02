import { berlinDate, daysBetween } from './berlin-time';
import type { Puzzle, Schedule } from './types';

export type TodaysPuzzle =
  | { status: 'not-started'; startsOn: string }
  | { status: 'active'; number: number; puzzle: Puzzle }
  // Today has a slot, but its puzzle has not been approved for players yet.
  | { status: 'unavailable'; number: number }
  | { status: 'finished' };

type Options = {
  schedule: Schedule;
  puzzles: Puzzle[];
  now: Date;
  /** Development only: also serve puzzles that are still drafts. */
  allowDrafts?: boolean;
};

/**
 * Today's puzzle. Its number is the count of Berlin days since the schedule's
 * start date, so every player sees the same one no matter when they open the
 * page.
 */
export function getTodaysPuzzle({
  schedule,
  puzzles,
  now,
  allowDrafts = false,
}: Options): TodaysPuzzle {
  const number = daysBetween(schedule.startDate, berlinDate(now)) + 1;
  if (number < 1) {
    return { status: 'not-started', startsOn: schedule.startDate };
  }

  const id = schedule.puzzleIds[number - 1];
  if (id === undefined) {
    return { status: 'finished' };
  }

  const puzzle = puzzles.find((candidate) => candidate.id === id);
  if (!puzzle || (puzzle.reviewStatus !== 'approved' && !allowDrafts)) {
    return { status: 'unavailable', number };
  }
  return { status: 'active', number, puzzle };
}

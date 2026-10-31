import { berlinDate, daysBetween } from './berlin-time';
import type { Puzzle, Schedule } from './types';

type TodaysPuzzle =
  | { status: 'not-started'; startsOn: string }
  | { status: 'active'; number: number; puzzle: Puzzle }
  | { status: 'finished' };

type Options = {
  schedule: Schedule;
  puzzles: Puzzle[];
  now: Date;
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
}: Options): TodaysPuzzle {
  const number = daysBetween(schedule.startDate, berlinDate(now)) + 1;
  if (number < 1) {
    return { status: 'not-started', startsOn: schedule.startDate };
  }
  const puzzle = puzzleForDay({ schedule, puzzles, number });
  return puzzle ? { status: 'active', number, puzzle } : { status: 'finished' };
}

type DayOptions = {
  schedule: Schedule;
  puzzles: Puzzle[];
  /** The day of the schedule, which is also the puzzle number. */
  number: number;
};

/** The puzzle that ran (or runs) on a given day, or null outside the schedule. */
export function puzzleForDay({
  schedule,
  puzzles,
  number,
}: DayOptions): Puzzle | null {
  const id = schedule.puzzleIds[number - 1];
  return puzzles.find((candidate) => candidate.id === id) ?? null;
}

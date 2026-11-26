import puzzlesJson from './content/puzzles.json';
import scheduleJson from './content/schedule.json';
import { puzzleForDay } from './schedule';
import type { Puzzle, Schedule } from './types';
import {
  validatePollIds,
  validatePuzzle,
  validatePuzzleOrder,
} from './validate';

// Swapping, reordering or dropping a puzzle only touches these two JSON files
// (see docs/stimmts/CONTENT.md).
export const PUZZLES: Puzzle[] = (puzzlesJson as unknown[]).map(validatePuzzle);

validatePollIds(PUZZLES);

const PUZZLE_ORDER: string[] = validatePuzzleOrder(scheduleJson, PUZZLES);

export const PUZZLE_COUNT = PUZZLE_ORDER.length;

/**
 * The title of puzzle `number` in the running order, or null outside it.
 * The order alone decides the number, so this needs no launch date.
 */
export function puzzleTitle(number: number): string | null {
  return (
    puzzleForDay({
      schedule: { puzzleIds: PUZZLE_ORDER },
      puzzles: PUZZLES,
      number,
    })?.title ?? null
  );
}

/** The committed running order, starting on the launch date. */
export function createSchedule(launchDate: string): Schedule {
  return { startDate: launchDate, puzzleIds: PUZZLE_ORDER };
}

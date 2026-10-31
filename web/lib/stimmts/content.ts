import puzzlesJson from './content/puzzles.json';
import scheduleJson from './content/schedule.json';
import type { Puzzle, Schedule } from './types';
import { validatePuzzle, validatePuzzleOrder } from './validate';

// Swapping, reordering or dropping a puzzle only touches these two JSON files
// (see docs/stimmts/CONTENT.md).
export const PUZZLES: Puzzle[] = (puzzlesJson as unknown[]).map(validatePuzzle);

const PUZZLE_ORDER: string[] = validatePuzzleOrder(scheduleJson, PUZZLES);

export const PUZZLE_COUNT = PUZZLE_ORDER.length;

/** The committed running order, starting on the launch date. */
export function createSchedule(launchDate: string): Schedule {
  return { startDate: launchDate, puzzleIds: PUZZLE_ORDER };
}

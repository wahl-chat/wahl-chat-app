import puzzlesJson from './content/puzzles.json';
import scheduleJson from './content/schedule.json';
import type { Puzzle, Schedule } from './types';
import { validatePuzzle, validateSchedule } from './validate';

// Swapping, reordering or dropping a puzzle only touches these two JSON files.
export const PUZZLES: Puzzle[] = (puzzlesJson as unknown[]).map(validatePuzzle);

export const SCHEDULE: Schedule = validateSchedule(scheduleJson, PUZZLES);

import puzzlesJson from '@/lib/stimmts/fixtures/puzzles.json';
import tankrabattJson from '@/lib/stimmts/fixtures/tankrabatt.json';
import type { Puzzle } from '@/lib/stimmts/types';
import { validatePuzzle } from '@/lib/stimmts/validate';

/**
 * Three puzzles for the tests to build on. The real puzzles in content/ are
 * edited and replaced as the game runs; tests about game logic must not break
 * when they are.
 */
export const FIXTURE_PUZZLES: Puzzle[] = (puzzlesJson as unknown[]).map(
  validatePuzzle,
);

/**
 * The Tankrabatt vote as it ran on day 1, kept apart from the three above so
 * the schedule tests keep their length: the result screen's counts are
 * checked against the numbers the designs were drawn with.
 */
export const TANKRABATT_PUZZLE: Puzzle = validatePuzzle(tankrabattJson);

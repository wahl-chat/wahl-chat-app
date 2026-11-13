import puzzlesJson from '@/lib/stimmts/fixtures/puzzles.json';
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

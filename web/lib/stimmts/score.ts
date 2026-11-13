import type { Guesses, Puzzle, VoteAnswer } from './types';

type PartyScore = {
  partyId: string;
  /** Null when the player never answered for this party. */
  guess: VoteAnswer | null;
  actual: VoteAnswer;
  correct: boolean;
};

export type PuzzleScore = {
  correct: number;
  total: number;
  /** In seating order, like the puzzle. */
  parties: PartyScore[];
};

export function scorePuzzle(puzzle: Puzzle, guesses: Guesses): PuzzleScore {
  const parties = puzzle.parties.map((party) => {
    const guess = guesses[party.partyId] ?? null;
    return {
      partyId: party.partyId,
      guess,
      actual: party.answer,
      correct: guess === party.answer,
    };
  });
  return {
    correct: parties.filter((party) => party.correct).length,
    total: parties.length,
    parties,
  };
}

export function isComplete(puzzle: Puzzle, guesses: Guesses): boolean {
  return puzzle.parties.every((party) => guesses[party.partyId] !== undefined);
}

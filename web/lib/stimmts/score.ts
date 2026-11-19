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

export type VoteTotals = {
  yes: number;
  no: number;
  abstain: number;
  noShow: number;
};

/**
 * The whole Bundestag's vote, summed over the Fraktionen. Members without one
 * are only drawn in the chamber; their votes are not in the puzzle.
 */
export function voteTotals(puzzle: Puzzle): VoteTotals {
  return puzzle.parties.reduce(
    (totals, party) => ({
      yes: totals.yes + party.yes,
      no: totals.no + party.no,
      abstain: totals.abstain + party.abstain,
      noShow: totals.noShow + party.noShow,
    }),
    { yes: 0, no: 0, abstain: 0, noShow: 0 },
  );
}

// The feed's words (abgeordnetenwatch's "Nicht beteiligt"), so the game and
// the feed count a vote the same way.
const COUNT_LABELS: Record<keyof VoteTotals, string> = {
  yes: 'Ja',
  no: 'Nein',
  abstain: 'Enthalten',
  noShow: 'Nicht beteiligt',
};

/** "433 Ja", "127 Nein", "0 Enthalten", "67 Nicht beteiligt", in that order. */
export function voteCountLabels(
  totals: VoteTotals,
): { vote: keyof VoteTotals; label: string }[] {
  return (['yes', 'no', 'abstain', 'noShow'] as const).map((vote) => ({
    vote,
    label: `${totals[vote]} ${COUNT_LABELS[vote]}`,
  }));
}

import type { PartyState } from './chamber-state';
import { seatCount } from './hemicycle';
import { OUTCOME_LABELS } from './labels';
import type { Guesses, Puzzle } from './types';

/** The screens of one puzzle, in the order a player meets them. */
export type Phase = 'briefing' | 'answering' | 'reveal' | 'result';

/** The party being asked: the first one, in seating order, without a tip. */
export function currentPartyIndex(puzzle: Puzzle, guesses: Guesses): number {
  return puzzle.parties.findIndex(
    (party) => guesses[party.partyId] === undefined,
  );
}

/**
 * What the chamber shows on each screen. While answering, the party being
 * asked stands out and the ones still to come are dimmed; on the reveal, a
 * party not yet turned over shows the player's tip and can be tapped.
 */
export function chamberStates(
  puzzle: Puzzle,
  phase: Phase,
  guesses: Guesses,
  revealed: ReadonlySet<string>,
): Record<string, PartyState> {
  const asked = currentPartyIndex(puzzle, guesses);
  return Object.fromEntries(
    puzzle.parties.map((party, index): [string, PartyState] => {
      const guess = guesses[party.partyId];
      if (phase === 'briefing') {
        return [party.partyId, { mode: 'pending' }];
      }
      if (revealed.has(party.partyId)) {
        return [party.partyId, { mode: 'revealed' }];
      }
      if (guess) {
        return [
          party.partyId,
          { mode: 'guessed', guess, tappable: phase === 'reveal' },
        ];
      }
      if (phase === 'answering' && index === asked) {
        return [party.partyId, { mode: 'active' }];
      }
      return [party.partyId, { mode: 'pending', dim: phase === 'answering' }];
    }),
  );
}

/** The two lines in the chamber's hollow centre. */
export function chamberCenter(
  puzzle: Puzzle,
  phase: Phase,
  guesses: Guesses,
  revealed: ReadonlySet<string>,
): { big: string; small: string } {
  if (phase === 'briefing') {
    const seats =
      puzzle.parties.reduce((sum, party) => sum + seatCount(party), 0) +
      puzzle.unaffiliated;
    return { big: String(seats), small: 'Sitze' };
  }
  if (phase === 'answering') {
    const asked = currentPartyIndex(puzzle, guesses);
    return {
      big: `${asked + 1} / ${puzzle.parties.length}`,
      small: 'Parteien',
    };
  }
  // The tally builds up as parties are turned over.
  const shown = puzzle.parties.filter((party) => revealed.has(party.partyId));
  const yes = shown.reduce((sum, party) => sum + party.yes, 0);
  const no = shown.reduce((sum, party) => sum + party.no, 0);
  const all = shown.length === puzzle.parties.length;
  return {
    big: `${yes} : ${no}`,
    small: all ? OUTCOME_LABELS[puzzle.outcome] : 'Ja : Nein',
  };
}

/** The whole Bundestag's Ja and Nein, for the outcome line. */
export function voteTotals(puzzle: Puzzle): { yes: number; no: number } {
  return puzzle.parties.reduce(
    (totals, party) => ({
      yes: totals.yes + party.yes,
      no: totals.no + party.no,
    }),
    { yes: 0, no: 0 },
  );
}

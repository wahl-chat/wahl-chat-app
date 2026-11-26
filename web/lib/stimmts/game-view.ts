import type { PartyState } from './chamber-state';
import { seatCount } from './hemicycle';
import { OUTCOME_LABELS } from './labels';
import type { Guesses, Puzzle } from './types';

/** The screens of one puzzle, in the order a player meets them. */
export type Phase = 'briefing' | 'answering' | 'review' | 'reveal' | 'result';

/**
 * Which screen a puzzle is on, from what is saved and what this page has
 * done. Every party with a tip means the review even without `started`, so a
 * reload during the review resumes there.
 */
export function gamePhase({
  started,
  complete,
  finished,
  showResult,
}: {
  started: boolean;
  complete: boolean;
  finished: boolean;
  showResult: boolean;
}): Phase {
  if (finished) {
    return showResult ? 'result' : 'reveal';
  }
  if (complete) {
    return 'review';
  }
  return started ? 'answering' : 'briefing';
}

/** The party being asked: the first one, in seating order, without a tip. */
export function currentPartyIndex(puzzle: Puzzle, guesses: Guesses): number {
  return puzzle.parties.findIndex(
    (party) => guesses[party.partyId] === undefined,
  );
}

/**
 * The party the guess card asks, by seating index: the one being edited if
 * any, else the first without a tip (-1 on the review, where none is left).
 */
export function askedIndex(
  puzzle: Puzzle,
  guesses: Guesses,
  edited?: string,
): number {
  return edited
    ? puzzle.parties.findIndex((party) => party.partyId === edited)
    : currentPartyIndex(puzzle, guesses);
}

/**
 * What the chamber shows on each screen. While answering, the party being
 * asked stands out and the ones still to come are dimmed; on the review
 * every tip shows, none dimmed, unless a party is being edited; on the
 * reveal, a party not yet turned over shows the player's tip and can be
 * tapped. `edited` is an answered party the card asks again.
 */
export function chamberStates(
  puzzle: Puzzle,
  phase: Phase,
  guesses: Guesses,
  revealed: ReadonlySet<string>,
  edited?: string,
): Record<string, PartyState> {
  const asking = phase === 'answering' || phase === 'review';
  const asked = asking ? askedIndex(puzzle, guesses, edited) : -1;
  return Object.fromEntries(
    puzzle.parties.map((party, index): [string, PartyState] => {
      const guess = guesses[party.partyId];
      if (phase === 'briefing') {
        return [party.partyId, { mode: 'pending' }];
      }
      if (revealed.has(party.partyId)) {
        return [
          party.partyId,
          { mode: 'revealed', tappable: phase === 'reveal' },
        ];
      }
      if (index === asked) {
        return [party.partyId, { mode: 'active' }];
      }
      if (guess) {
        return [
          party.partyId,
          { mode: 'guessed', guess, tappable: phase === 'reveal' },
        ];
      }
      return [party.partyId, { mode: 'pending', dim: phase === 'answering' }];
    }),
  );
}

/** True once every party of the puzzle has been turned over. */
export function allRevealed(
  puzzle: Puzzle,
  revealed: ReadonlySet<string>,
): boolean {
  return puzzle.parties.every((party) => revealed.has(party.partyId));
}

/** How long the finished tally stays on screen before the result follows. */
export const AUTO_RESULT_DELAY_MS = 1500;

/** Without motion nothing needs time to land, so the move is almost at once. */
export function autoResultDelay(reduceMotion: boolean): number {
  return reduceMotion ? 300 : AUTO_RESULT_DELAY_MS;
}

/** The two lines in the chamber's hollow centre. */
export function chamberCenter(
  puzzle: Puzzle,
  phase: Phase,
  guesses: Guesses,
  revealed: ReadonlySet<string>,
  edited?: string,
): { big: string; small: string } {
  if (phase === 'briefing') {
    const seats =
      puzzle.parties.reduce((sum, party) => sum + seatCount(party), 0) +
      puzzle.unaffiliated;
    return { big: String(seats), small: 'Sitze' };
  }
  if (phase === 'answering' || phase === 'review') {
    // On the review no party is left to ask unless one is being edited.
    const asked = askedIndex(puzzle, guesses, edited);
    const count = asked === -1 ? puzzle.parties.length : asked + 1;
    return {
      big: `${count} / ${puzzle.parties.length}`,
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

type RevealSelection = {
  revealed: ReadonlySet<string>;
  /** The party whose counts are open under its row; one at a time. */
  open: string | null;
};

/**
 * A tap on a party, in "Deine Tipps" or on its logo in the chamber: the
 * first tap turns it over and opens its counts, later taps open and close
 * them. Opening one party closes any other.
 */
export function selectParty(
  { revealed, open }: RevealSelection,
  partyId: string,
): RevealSelection {
  if (!revealed.has(partyId)) {
    return { revealed: new Set(revealed).add(partyId), open: partyId };
  }
  return { revealed, open: open === partyId ? null : partyId };
}

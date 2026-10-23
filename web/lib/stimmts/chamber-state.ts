import { type Seat, seatCount } from './hemicycle';
import { ANSWER_LABELS, partyLabel } from './labels';
import type { PartyResult, VoteAnswer } from './types';

/**
 * What the chamber shows for one party. It only ever shows what parties did
 * (or what the player guessed they did, as hollow rings); how the player did
 * is shown elsewhere, so no mark here can be read as a party's vote.
 */
export type PartyState =
  /** Not asked or not revealed yet; `dim` while another party is asked. */
  | { mode: 'pending'; dim?: boolean }
  /** Being asked right now. */
  | { mode: 'active' }
  /** Answered: rings in the guessed vote's colour. */
  | { mode: 'guessed'; guess: VoteAnswer; tappable?: boolean }
  /** Turned over: filled with the real split. */
  | { mode: 'revealed' };

export type SeatLook =
  | 'pending'
  | 'active'
  | `guess-${VoteAnswer}`
  | 'yes'
  | 'no'
  | 'abstain'
  | 'absent'
  | 'unaffiliated';

const PENDING: PartyState = { mode: 'pending' };

export function partyState(
  states: Record<string, PartyState>,
  partyId: string,
): PartyState {
  return states[partyId] ?? PENDING;
}

export function seatLook(seat: Seat, state: PartyState): SeatLook {
  if (seat.partyId === null || seat.vote === null) {
    return 'unaffiliated';
  }
  switch (state.mode) {
    case 'revealed':
      return seat.vote;
    case 'guessed':
      return `guess-${state.guess}`;
    case 'active':
      return 'active';
    default:
      return 'pending';
  }
}

function describe(party: PartyResult, state: PartyState): string {
  switch (state.mode) {
    case 'revealed':
      return `${party.yes} Ja, ${party.no} Nein, ${party.abstain} Enthaltung, ${party.noShow} abwesend`;
    case 'guessed':
      return `dein Tipp: ${ANSWER_LABELS[state.guess]}`;
    case 'active':
      return 'wird gerade gefragt';
    default:
      return 'noch offen';
  }
}

/** Everything the chamber shows, read out for a screen reader. */
export function chamberLabel(
  parties: readonly PartyResult[],
  states: Record<string, PartyState>,
  unaffiliated: number,
): string {
  const total =
    parties.reduce((sum, party) => sum + seatCount(party), 0) + unaffiliated;
  const lines = parties.map(
    (party) =>
      `${partyLabel(party.partyId)}: ${describe(party, partyState(states, party.partyId))}`,
  );
  const extra =
    unaffiliated > 0
      ? ` ${unaffiliated} fraktionslose Abgeordnete am rechten Rand.`
      : '';
  return `Sitzverteilung im Bundestag, ${total} Sitze. ${lines.join('. ')}.${extra}`;
}

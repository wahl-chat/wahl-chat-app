import type { PuzzleOutcome, VoteAnswer } from './types';

export const ANSWER_LABELS: Record<VoteAnswer, string> = {
  yes: 'Ja',
  no: 'Nein',
  abstain: 'Enthaltung',
};

export const OUTCOME_LABELS: Record<PuzzleOutcome, string> = {
  accepted: 'angenommen',
  rejected: 'abgelehnt',
};

/** 2026-07-10 becomes "10. Juli 2026". */
export function formatDate(isoDate: string): string {
  return new Date(`${isoDate}T12:00:00Z`).toLocaleDateString('de-DE', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'Europe/Berlin',
  });
}

/** The order the answer buttons are shown in. */
export const ANSWER_ORDER: VoteAnswer[] = ['yes', 'no', 'abstain'];

const PARTY_LABELS: Record<string, string> = {
  linke: 'Die Linke',
  spd: 'SPD',
  gruene: 'Bündnis 90/Die Grünen',
  cdu: 'CDU/CSU',
  afd: 'AfD',
};

/** Falls back to the slug, so an unexpected party still shows up. */
export function partyLabel(partyId: string): string {
  return PARTY_LABELS[partyId] ?? partyId;
}

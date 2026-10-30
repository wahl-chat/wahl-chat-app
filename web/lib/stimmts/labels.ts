import { TIME_ZONE, calendarDay, daysBetween } from './berlin-time';
import type { BillDocument, PuzzleOutcome, VoteAnswer } from './types';

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
  return calendarDay(isoDate).toLocaleDateString('de-DE', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: TIME_ZONE,
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

const MONTHS = [
  'Januar',
  'Februar',
  'März',
  'April',
  'Mai',
  'Juni',
  'Juli',
  'August',
  'September',
  'Oktober',
  'November',
  'Dezember',
];

export const WEEKDAYS = [
  'Sonntag',
  'Montag',
  'Dienstag',
  'Mittwoch',
  'Donnerstag',
  'Freitag',
  'Samstag',
];

export function weekdayName(isoDate: string): string {
  return WEEKDAYS[calendarDay(isoDate).getUTCDay()];
}

/** The first three letters of the month, for a calendar leaf ("Jul"). */
export function monthShort(isoDate: string): string {
  return MONTHS[calendarDay(isoDate).getUTCMonth()].slice(0, 3);
}

export function dayOfMonth(isoDate: string): number {
  return calendarDay(isoDate).getUTCDate();
}

/** 2026-11-01 becomes "So 1.11.", as on a Stimmkarte. */
export function shortDay(isoDate: string): string {
  const day = calendarDay(isoDate);
  return `${weekdayName(isoDate).slice(0, 2)} ${day.getUTCDate()}.${day.getUTCMonth() + 1}.`;
}

/** 2026-06-08 becomes "08.06.2026", as printed on a Drucksache. */
export function dottedDate(isoDate: string): string {
  const [year, month, day] = isoDate.split('-');
  return `${day}.${month}.${year}`;
}

/**
 * How long ago a vote was, counted from the puzzle's day rather than the
 * player's clock, so every player reads the same on the same day.
 */
export function timeAgo(isoDate: string, fromIsoDate: string): string {
  const days = daysBetween(isoDate, fromIsoDate);
  if (days <= 0) {
    return 'heute';
  }
  if (days === 1) {
    return 'gestern';
  }
  if (days < 14) {
    return `vor ${days} Tagen`;
  }
  if (days < 60) {
    return `vor ${Math.round(days / 7)} Wochen`;
  }
  const months = Math.round(days / 30.44);
  if (months < 12) {
    return `vor ${months} Monaten`;
  }
  const years = Math.round(months / 12);
  return years === 1 ? 'vor einem Jahr' : `vor ${years} Jahren`;
}

/** "Ja bedeutet: dem … zustimmen." becomes "dem … zustimmen." */
export function yesMeaning(yesMeans: string): string {
  return yesMeans.replace(/^\s*Ja bedeutet:\s*/, '');
}

/**
 * Who submitted the bill, as the Drucksache's cover prints it. A long list of
 * members is shortened the way the Bundestag shortens it itself: "der
 * Abgeordneten A, B, weiterer Abgeordneter und der Fraktion der AfD".
 */
export function submitterLine(document: BillDocument): string {
  if ('initiator' in document) {
    return document.initiator;
  }
  const { members, fraktion } = document;
  const signed = document.memberCount ?? members.length;
  const names =
    signed > 2
      ? `${members.slice(0, 2).join(', ')}, weiterer Abgeordneter`
      : members.join(', ');
  return `der Abgeordneten ${names} und der Fraktion ${fraktion}`;
}

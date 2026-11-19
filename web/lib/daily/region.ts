import type { DigestParliamentId } from '@/lib/firebase/firebase.types';

type DailyState = {
  /** Only Länder whose Landtag the feed covers have one. None does yet:
   * abgeordnetenwatch publishes Landtag votes one to five months late, so a
   * Landtag's days would stay incomplete for months. The list stays, to show
   * the Länder that are coming. */
  parliament?: DigestParliamentId;
  /** Coat of arms, where an election image doubles as one. */
  sigil?: string;
};

/** All Bundesländer, keyed by ISO 3166-2 subdivision code without `DE-`.
 * Their names are in the `feed.parliaments` messages. */
export const DAILY_STATES: Record<string, DailyState> = {
  BW: {
    sigil: '/images/landtagswahl-baden-wuerttemberg-2026.webp',
  },
  BY: {},
  BE: {
    sigil: '/images/abgeordnetenhauswahl-berlin-2026.webp',
  },
  BB: {},
  HB: {},
  HH: {},
  HE: {},
  MV: {
    sigil: '/images/landtagswahl-mecklenburg-vorpommern-2026.webp',
  },
  NI: {},
  NW: {},
  RP: {
    sigil: '/images/landtagswahl-rheinland-pfalz-2026.webp',
  },
  SL: {},
  SN: {},
  ST: {
    sigil: '/images/landtagswahl-sachsen-anhalt-2026.webp',
  },
  SH: {},
  TH: {},
};

export const BUNDESTAG_SIGIL = '/images/bundestagswahl-2025.webp';

/** The Bundestag's code in a selection, next to the Länder codes. */
export const BUNDESTAG = 'DE';

/** Selected parliaments: `DE` for the Bundestag plus Länder with a covered
 * Landtag. Never empty; the Bundestag alone is the default. */
export type StateSelection = string[];

export const DEFAULT_SELECTION: StateSelection = [BUNDESTAG];

export const STATE_PARAM = 'land';
export const STATE_STORAGE_KEY = 'wahlchat-feed-land';

function isSelectable(code: string): boolean {
  return code === BUNDESTAG || DAILY_STATES[code]?.parliament !== undefined;
}

/** Comma-separated codes, e.g. `de,st`; unknown or uncovered codes drop out.
 * `undefined` when nothing valid is left, so a stored choice or the default
 * can decide. */
export function parseStateParam(
  value: string | string[] | null | undefined,
): StateSelection | undefined {
  const raw = Array.isArray(value) ? value.join(',') : value;
  const codes = [
    ...new Set(
      (raw ?? '')
        .split(',')
        .map((code) => code.trim().toUpperCase())
        .filter(isSelectable),
    ),
  ];
  return codes.length > 0 ? codes : undefined;
}

export function parliamentsFor(
  selection: StateSelection,
): DigestParliamentId[] {
  // Bundestag first, whatever order the codes came in.
  return [
    ...(selection.includes(BUNDESTAG) ? (['bundestag'] as const) : []),
    ...selection.flatMap((code) => DAILY_STATES[code]?.parliament ?? []),
  ];
}

/** Coat of arms for a selected code. */
export function sigilFor(code: string): string | undefined {
  return code === BUNDESTAG ? BUNDESTAG_SIGIL : DAILY_STATES[code]?.sigil;
}

import type { DigestParliamentId } from '@/lib/firebase/firebase.types';

/** Bundesländer the feed has a Landtag for. Keys are ISO 3166-2 subdivision
 * codes without the `DE-` prefix, which is what Vercel's
 * `x-vercel-ip-country-region` header carries. */
export const DAILY_STATES = {
  ST: { name: 'Sachsen-Anhalt', parliament: 'landtag_st' },
  BW: { name: 'Baden-Württemberg', parliament: 'landtag_bw' },
} as const satisfies Record<
  string,
  { name: string; parliament: DigestParliamentId }
>;

export type DailyStateId = keyof typeof DAILY_STATES;

/** `none` = Bundestag only (the user's state has no Landtag coverage yet). */
export type StateSelection = DailyStateId | 'none';

export const STATE_PARAM = 'land';

function isDailyState(value: string): value is DailyStateId {
  return Object.hasOwn(DAILY_STATES, value);
}

export function stateFromGeo(
  country: string | null | undefined,
  region: string | null | undefined,
): StateSelection {
  if (country?.toUpperCase() !== 'DE' || !region) {
    return 'none';
  }
  const code = region.toUpperCase();
  return isDailyState(code) ? code : 'none';
}

/** `undefined` when the param is absent or unknown, so geo can decide. */
export function parseStateParam(
  value: string | string[] | null | undefined,
): StateSelection | undefined {
  const raw = Array.isArray(value) ? value[0] : value;
  if (!raw) {
    return undefined;
  }
  const code = raw.toUpperCase();
  if (code === 'NONE') {
    return 'none';
  }
  return isDailyState(code) ? code : undefined;
}

export function parliamentsFor(
  selection: StateSelection,
): DigestParliamentId[] {
  return selection === 'none'
    ? ['bundestag']
    : ['bundestag', DAILY_STATES[selection].parliament];
}

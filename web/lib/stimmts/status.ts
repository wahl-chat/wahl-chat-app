import { isIsoDate } from './berlin-time';

/**
 * The game's switch, read from the Firestore doc system_status/stimmts
 * `{ enabled: boolean, launch_date: "YYYY-MM-DD" }`. The launch date is day 1.
 */
export type StimmtsStatus =
  | { enabled: false }
  | { enabled: true; launchDate: string };

/** The switch as the page knows it (see useStimmtsStatus). */
export type StatusState =
  | { kind: 'loading' }
  | { kind: 'unreachable' }
  | { kind: 'known'; status: StimmtsStatus };

export type Launch =
  | { kind: 'loading' }
  | { kind: 'unreachable' }
  | { kind: 'off' }
  | { kind: 'on'; launchDate: string };

/**
 * Reads the raw doc. Anything short of `enabled: true` with a real date is
 * off, so a missing doc or a typo in the console keeps the game hidden rather
 * than starting it on the wrong day.
 */
export function parseStimmtsStatus(data: unknown): StimmtsStatus {
  if (typeof data !== 'object' || data === null) {
    return { enabled: false };
  }
  const { enabled, launch_date: launchDate } = data as Record<string, unknown>;
  return enabled === true && isIsoDate(launchDate)
    ? { enabled: true, launchDate }
    : { enabled: false };
}

/**
 * Whether the game is on, and since when. Preview always plays: it keeps the
 * real launch date when there is one and otherwise starts today, so every
 * puzzle can be tried before the launch.
 */
export function resolveLaunch(
  state: StatusState,
  previewEnabled: boolean,
  today: string,
): Launch {
  if (state.kind === 'loading') {
    return state;
  }
  if (state.kind === 'known' && state.status.enabled) {
    return { kind: 'on', launchDate: state.status.launchDate };
  }
  if (previewEnabled) {
    return { kind: 'on', launchDate: today };
  }
  return state.kind === 'unreachable' ? state : { kind: 'off' };
}

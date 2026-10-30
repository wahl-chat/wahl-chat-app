import { berlinDate, isIsoDate } from './berlin-time';

/**
 * The game's switch, read from the Firestore doc system_status/stimmts
 * `{ enabled: boolean, launch_date: "YYYY-MM-DD" }`. The launch date is day 1.
 */
export type StimmtsStatus =
  | { enabled: false }
  | { enabled: true; launchDate: string };

export type Availability =
  | { status: 'off' }
  | { status: 'not-started'; launchDate: string }
  | { status: 'running'; launchDate: string };

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

export function resolveAvailability(
  status: StimmtsStatus,
  now: Date,
): Availability {
  if (!status.enabled) {
    return { status: 'off' };
  }
  const { launchDate } = status;
  // YYYY-MM-DD strings sort like the dates they name.
  return berlinDate(now) < launchDate
    ? { status: 'not-started', launchDate }
    : { status: 'running', launchDate };
}

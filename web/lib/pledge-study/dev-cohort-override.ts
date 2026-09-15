import type { StudyCohort } from './study-config';

/**
 * Dev-only cohort override for the PledgeTracker study.
 *
 * The cohort is a deterministic hash of the anonymous uid, so without this the
 * only way to see the other arm locally is to clear site data until the hash
 * lands the other way. The override is kept in localStorage (so it survives a
 * reload) and applied over the Firestore read on hydrate.
 *
 * `study_participants` is NEVER written from here: dev fiddling must not be
 * able to overwrite a real hashed assignment or contaminate the analysis data.
 *
 * NODE_ENV is inlined by Next at build time, so in a production build every
 * function below is inert. The dev bar module is still emitted into the client
 * bundle (a 'use client' import becomes a client reference that survives
 * tree-shaking), but it can never render and these never touch storage.
 */
export const STUDY_DEV_TOOLS = process.env.NODE_ENV === 'development';

const STORAGE_KEY = 'wahlchat.studyCohortOverride';

function isCohort(value: string | null): value is StudyCohort {
  return value === 'control' || value === 'experimental';
}

export function readDevCohortOverride(): StudyCohort | undefined {
  if (!STUDY_DEV_TOOLS || typeof window === 'undefined') return undefined;
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return isCohort(stored) ? stored : undefined;
  } catch {
    // Storage can throw in private mode or when site data is blocked.
    return undefined;
  }
}

export function writeDevCohortOverride(cohort: StudyCohort): void {
  if (!STUDY_DEV_TOOLS || typeof window === 'undefined') return;
  try {
    localStorage.setItem(STORAGE_KEY, cohort);
  } catch {
    // Ignore: the store still holds the override for this page load.
  }
}

export function clearDevCohortOverride(): void {
  if (!STUDY_DEV_TOOLS || typeof window === 'undefined') return;
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Ignore.
  }
}

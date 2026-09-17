'use client';

import { isProlificStudy } from '@/lib/prolific-study/prolific-metadata';
import type {
  StudyCohort,
  StudyConsentAnswer,
  StudyParticipation,
} from './types';

/**
 * Forcing a study variant from the URL, so any arm can be demonstrated in dev
 * AND in production — including before launch, when the kill switch is still
 * off and nothing study-related would otherwise render.
 *
 * The values are opaque on purpose: a participant glancing at the address bar
 * should not be able to read their arm off it. That is the whole bar. There is
 * deliberately NO signing or server-side validation — this repo is public and
 * the client bundle is inspectable, so anything stronger would be theatre.
 *
 * Sessions forced this way are flagged in Firestore (assignment_source:
 * 'override') and MUST be excluded from analysis; the real 50:50 hash is never
 * touched. Use a fresh browser profile for override links: opening one in a
 * profile that is already a genuine participant flags that real record.
 */

export const STUDY_OVERRIDE_PARAM = 'sg';

export type StudyOverrideVariant = 'control' | 'manipulation' | 'declined';

export type StudyOverride = {
  variant: StudyOverrideVariant;
  participation: StudyParticipation;
  consent: StudyConsentAnswer;
  /** Absent for the declined variant — non-participants have no arm. */
  cohort?: StudyCohort;
};

const STORAGE_KEY = 'wahlchat.studyVariantOverride';

/** Clears a stored override; needed because the value outlives the URL. */
const RESET_TOKEN = 'off';

const VARIANTS: Record<string, StudyOverride> = {
  a: {
    variant: 'control',
    participation: 'experimental',
    consent: 'accepted',
    cohort: 'control',
  },
  b: {
    variant: 'manipulation',
    participation: 'experimental',
    consent: 'accepted',
    cohort: 'manipulation',
  },
  x: {
    variant: 'declined',
    participation: 'regular',
    consent: 'declined',
  },
};

function fromToken(token: string | null): StudyOverride | undefined {
  return token ? VARIANTS[token] : undefined;
}

function readStored(): StudyOverride | undefined {
  try {
    return fromToken(sessionStorage.getItem(STORAGE_KEY));
  } catch {
    // Storage blocked (private mode, blocked site data).
    return undefined;
  }
}

/**
 * The active override, URL first then sessionStorage. Pure — no writes.
 *
 * Always undefined for Prolific participants: they are in a different study,
 * and enrolling them in this one would corrupt both.
 */
export function readStudyOverride(): StudyOverride | undefined {
  if (typeof window === 'undefined' || isProlificStudy()) {
    return undefined;
  }
  const token = new URLSearchParams(window.location.search).get(
    STUDY_OVERRIDE_PARAM,
  );
  if (token === RESET_TOKEN) {
    return undefined;
  }
  return fromToken(token) ?? readStored();
}

/**
 * readStudyOverride() plus persistence, so the override survives client-side
 * navigation that drops the query string. Call once, from an effect.
 */
export function captureStudyOverride(): StudyOverride | undefined {
  if (typeof window === 'undefined' || isProlificStudy()) {
    return undefined;
  }
  const token = new URLSearchParams(window.location.search).get(
    STUDY_OVERRIDE_PARAM,
  );
  if (token === RESET_TOKEN) {
    clearStudyOverride();
    return undefined;
  }
  const fromUrl = fromToken(token);
  if (fromUrl && token) {
    try {
      sessionStorage.setItem(STORAGE_KEY, token);
    } catch {
      // Storage unavailable; the store still holds it for this page load.
    }
    return fromUrl;
  }
  return readStored();
}

export function clearStudyOverride(): void {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Ignore.
  }
}

'use client';

import type { StudyCohort } from './types';

/**
 * PledgeTracker study configuration (the Vlachos-group experiment).
 *
 * Cohort assignment is a deterministic hash of the anonymous Firebase uid, so
 * a participant's group is stable across reloads with no network round trip;
 * the assignment is ALSO persisted to their study_participants doc at consent
 * time, which is the source of truth for analysis. The study runs only in the
 * two contexts below and only while the Firestore kill switch
 * (system_status/pledge_study {enabled: true}) is on — the safe default is
 * off. The dedicated feature-flag tooling planned for October can replace
 * this mechanism without touching the persisted assignments.
 */

export const STUDY_CONTEXT_IDS = [
  'abgeordnetenhauswahl-berlin-2026',
  'landtagswahl-mecklenburg-vorpommern-2026',
] as const;

export type QuestionnaireTrigger = 'second_answer' | 'absolute_timer';

// The data vocabulary lives in ./types (a non-client module, because the
// Firestore documents it describes are read by server code too).
export type {
  StudyCohort,
  StudyConsentAnswer,
  StudyParticipation,
} from './types';

// Questionnaire prompt timing — named constants so the researchers can tune
// without a code hunt (see the study runbook in AGENTS.md).
//
// Nothing about the prompt depends on PledgeTracker any more. Both triggers
// are reachable by BOTH arms, which is what finally makes the "identical for
// both cohorts" claim true: the modal-based triggers this replaced could only
// ever fire for the manipulation arm, so the users who saw the feature were
// prompted on paths a control user could never reach — differential prompt
// exposure by arm, in the one instrument measuring the outcome.
//
// The absolute fallback is anchored to the FIRST completed answer and only
// fires if nothing has prompted yet: it exists so a user who never reaches a
// second message is still asked once, not to re-tap someone already asked.
export const ABSOLUTE_FALLBACK_MS = 60_000;
export const MAX_PROMPTS = 2; // hard cap, persisted — never nag past this

// Changing the salt reshuffles ALL assignments — never change it while the
// study is running.
const STUDY_SALT = 'pledge-study-2026';

export function isStudyContext(contextId?: string | null): boolean {
  return (
    !!contextId && (STUDY_CONTEXT_IDS as readonly string[]).includes(contextId)
  );
}

/**
 * Deterministic p=0.5 cohort from the anonymous uid (FNV-1a over uid+salt).
 * Stable per browser profile; a second device is a new participant — an
 * accepted limitation of anonymous auth.
 */
export function assignCohort(uid: string): StudyCohort {
  const input = uid + STUDY_SALT;
  let hash = 0x811c9dc5;
  for (let i = 0; i < input.length; i++) {
    hash ^= input.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0) % 2 === 0 ? 'control' : 'manipulation';
}

/**
 * The study questionnaire's Fillout form.
 *
 * Hardcoded like every other Fillout form in this app (survey-banner, login
 * reminder, wahl-swiper) so the questionnaire works on a fresh checkout and on
 * both deployments with no env setup — a reviewer can test the flow by
 * cloning, and dev/prod need no Vercel variable. A form id is public anyway:
 * it is in the URL every respondent sees, and this repo is public.
 *
 * The study's real off-switch is the Firestore kill switch
 * (system_status/pledge_study), which takes effect instantly and needs no
 * deploy — so the questionnaire does not need a second one.
 */
export const STUDY_QUESTIONNAIRE_FORM_ID = 's9muKGX2zcus';

/**
 * Fillout form id to open, parsed from NEXT_PUBLIC_STUDY_QUESTIONNAIRE_URL
 * when that is set (point a branch at a test form by pasting its link, e.g.
 * `https://forms.fillout.com/t/<id>`; a bare id works too), otherwise the
 * default above.
 *
 * `user_id`, `chat_session_id` and `cohort` are passed to the embed as
 * parameters, matching the hidden fields on the form, so an export is
 * self-contained. Passing the cohort is a deliberate reversal of the original
 * "never unblind" rule: it does put the arm in the iframe URL where a curious
 * participant could read it. The arm is already inferable from whether
 * PledgeTracker rendered, and the analysis join on `user_id` remains the
 * authoritative source — `study_participants/{uid}.cohort`, which alone
 * carries `assignment_source` and so distinguishes real participants from
 * ?sg= testers.
 */
export function questionnaireFormId(): string {
  const configured = process.env.NEXT_PUBLIC_STUDY_QUESTIONNAIRE_URL?.trim();
  if (!configured) {
    return STUDY_QUESTIONNAIRE_FORM_ID;
  }
  if (!configured.includes('/')) {
    return configured;
  }
  try {
    const id = new URL(configured).pathname.split('/').filter(Boolean).pop();
    if (id) {
      return id;
    }
  } catch {
    // Not a parseable URL — fall through to the warning.
  }
  console.warn(
    '[Study] NEXT_PUBLIC_STUDY_QUESTIONNAIRE_URL is not a Fillout form link or id — using the default form',
  );
  return STUDY_QUESTIONNAIRE_FORM_ID;
}

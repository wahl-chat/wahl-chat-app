'use client';

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

export type StudyCohort = 'control' | 'experimental';
export type StudyConsentAnswer = 'accepted' | 'declined';
export type QuestionnaireTrigger = 'timer' | 'modal_close' | 'longstop';

// Questionnaire prompt timing — named constants so the researchers can tune
// without a code hunt (see the study runbook in AGENTS.md).
export const QUESTIONNAIRE_DELAY_MS = 15_000; // after the first answer completes
export const MODAL_LONGSTOP_MS = 90_000; // catches a never-closed pledge modal
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
  return (hash >>> 0) % 2 === 0 ? 'control' : 'experimental';
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
 * `user_id` and `chat_session_id` are passed to the embed as parameters. The
 * cohort is NEVER passed, so participants cannot unblind themselves.
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

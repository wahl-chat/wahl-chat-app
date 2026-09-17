/**
 * Shared vocabulary for the PledgeTracker study.
 *
 * Deliberately NOT a 'use client' module: these types describe Firestore
 * documents and are imported by server code as well as the browser.
 *
 * Two separate ideas, kept separate so neither word does double duty:
 *
 * - participation — does this user take part in the study at all?
 * - cohort        — for a participant, which arm are they in?
 *
 * "experimental" therefore means "in the experiment", never "sees the
 * feature". The arm that sees PledgeTracker is 'manipulation'.
 */

/** Does the user take part in the study? Mirrors the consent answer. */
export type StudyParticipation = 'experimental' | 'regular';

/** Which arm a participant is in. Only participants have one. */
export type StudyCohort = 'control' | 'manipulation';

export type StudyConsentAnswer = 'accepted' | 'declined';

/**
 * How a participant's cohort was decided. 'hash' is the real deterministic
 * 50:50 assignment; 'override' means a ?sg= link forced it, and those rows
 * must be excluded from analysis. Absent on records written before this
 * field existed, which are all 'hash'.
 */
export type StudyAssignmentSource = 'hash' | 'override';

/** Consent answer -> participation, so the two can never disagree. */
export function participationFor(
  consent: StudyConsentAnswer,
): StudyParticipation {
  return consent === 'accepted' ? 'experimental' : 'regular';
}

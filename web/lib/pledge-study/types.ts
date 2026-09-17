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
 * Which of the two consent screens the answer was given on. The dialog asks
 * twice: a short 'ask' ("Machst du mit?"), then, only after a "Ja", the full
 * 'consent' Einverständniserklärung. An acceptance can only happen on
 * 'consent'; a decline can happen on either, and the two mean very different
 * things — refusing the one-line ask is not the same as reading the formal
 * text and backing out.
 */
export type StudyConsentStage = 'ask' | 'consent';

/**
 * How a decline was expressed: 'explicit' is a "Nein" button, 'dismissed' is
 * Escape / overlay click / drawer swipe, which the dialog also persists as a
 * decline. Kept apart so a non-answer is not read as a refusal in the
 * analysis. Note that closing the tab leaves no record at all.
 */
export type StudyDeclineReason = 'explicit' | 'dismissed';

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

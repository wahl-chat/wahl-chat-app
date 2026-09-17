import {
  ABSOLUTE_FALLBACK_MS,
  MAX_PROMPTS,
  SECOND_ANSWER_DELAY_MS,
} from './study-config';
import type { StudyConsentAnswer } from './types';

/**
 * The questionnaire's decision logic, kept pure and away from the effects that
 * schedule it — the same split as gate.ts, and for the same reason: this is
 * the part that decides who gets asked, so it has to be readable and testable
 * without a DOM.
 *
 * Deliberately cohort-blind. Nothing here may consult the arm or PledgeTracker
 * state; if it did, the two groups would be asked on different terms and the
 * questionnaire would measure the manipulation as well as the outcome.
 */

/** May a prompt be shown at all right now? */
export function isPromptEligible({
  consent,
  questionnaireClicked,
  promptCount,
  promptShowing,
}: {
  consent: StudyConsentAnswer | undefined;
  questionnaireClicked: boolean;
  promptCount: number;
  promptShowing: boolean;
}): boolean {
  return (
    consent === 'accepted' &&
    !questionnaireClicked &&
    promptCount < MAX_PROMPTS &&
    !promptShowing
  );
}

/**
 * Milliseconds still to wait on the absolute fallback, given when the first
 * answer completed. Clamped at zero so a reload well past the deadline prompts
 * promptly instead of starting the minute over — the stamp is the anchor, not
 * the moment the effect happened to mount.
 */
export function absoluteFallbackRemainingMs(
  firstAnswerCompletedAt: number,
  now: number,
): number {
  return Math.max(0, ABSOLUTE_FALLBACK_MS - (now - firstAnswerCompletedAt));
}

/**
 * Milliseconds still to wait after the second answer landed. Same clamping
 * rule as above, and anchored to the stamp rather than to when the effect
 * mounted, so switching chats mid-wait does not restart the countdown.
 */
export function secondAnswerDelayRemainingMs(
  secondAnswerCompletedAt: number,
  now: number,
): number {
  return Math.max(0, SECOND_ANSWER_DELAY_MS - (now - secondAnswerCompletedAt));
}

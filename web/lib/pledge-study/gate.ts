import type { StudyCohort, StudyConsentAnswer } from './types';

/**
 * THE scientific core of the study: who sees PledgeTracker.
 *
 * The kill switch (system_status/pledge_study) is the OUTERMOST gate and
 * governs the feature, not merely the experiment: while it is off, nobody sees
 * PledgeTracker in any context. PledgeTracker is new and is only meant to ship
 * inside a study for now, so "off" has to mean off everywhere — it must never
 * quietly become a full rollout to every election.
 *
 * With the switch on, a study context admits ONLY consented participants in
 * the manipulation arm: control sees nothing (that is the comparison), and
 * non-consented/declined users see nothing either — anyone pre-exposed who
 * later consents into the control group would be contaminated. Any other
 * context is the ordinary product and shows the feature to everyone.
 *
 * An unknown switch state (undefined) is folded in with off on purpose: a
 * brief flash of the pledge card for a user who then lands in control would
 * be exposure that cannot be undone.
 */
export function isPledgeTrackerAllowed({
  inStudyContext,
  studyEnabled,
  consent,
  cohort,
}: {
  inStudyContext: boolean;
  studyEnabled: boolean | undefined;
  consent: StudyConsentAnswer | undefined;
  cohort: StudyCohort | undefined;
}): boolean {
  if (!studyEnabled) {
    return false;
  }
  if (!inStudyContext) {
    return true;
  }
  return consent === 'accepted' && cohort === 'manipulation';
}

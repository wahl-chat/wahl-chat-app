import type { StudyCohort } from './types';

/**
 * THE scientific core of the study: who sees PledgeTracker.
 *
 * The kill switch (system_status/pledge_study) is the OUTERMOST gate and
 * governs the feature, not merely the experiment: while it is off, nobody sees
 * PledgeTracker in any context. PledgeTracker is new and is only meant to ship
 * inside a study for now, so "off" has to mean off everywhere — it must never
 * quietly become a full rollout to every election.
 *
 * With the switch on, a study context admits the manipulation arm and nobody
 * else. THE ARM ALONE DECIDES — the consent answer does not. Everyone who
 * answers the dialog is assigned an arm, including those who decline, because
 * consent governs the research instruments (the questionnaire) while the arm
 * governs which version of the product a user gets, and both arms are ordinary
 * product experiences.
 *
 * Pre-exposure cannot contaminate anyone here: the arm is a deterministic
 * hash(uid+salt), so a given uid's arm is the same whenever it is computed and
 * there is no "later assignment" to spoil. A user who has not answered at all
 * has no arm and therefore sees nothing.
 *
 * An unknown switch state (undefined) is folded in with off on purpose: a
 * brief flash of the pledge card for a user who belongs in control would be
 * exposure that cannot be undone.
 */
export function isPledgeTrackerAllowed({
  inStudyContext,
  studyEnabled,
  cohort,
}: {
  inStudyContext: boolean;
  studyEnabled: boolean | undefined;
  cohort: StudyCohort | undefined;
}): boolean {
  if (!studyEnabled) {
    return false;
  }
  if (!inStudyContext) {
    return true;
  }
  return cohort === 'manipulation';
}

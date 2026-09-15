import type { StudyCohort, StudyConsentAnswer } from './study-config';

/**
 * THE scientific core of the study: who sees PledgeTracker.
 *
 * Outside a study context, or while the study is switched off, the product is
 * unchanged. Inside a study context with the study on, ONLY consented
 * experimental participants see the feature: the control group sees nothing
 * (that is the comparison), and non-consented/declined users see nothing
 * either — anyone pre-exposed who later consents into the control group would
 * be contaminated.
 *
 * While the kill-switch state is still unknown (undefined) in a study
 * context, the feature stays hidden: a brief flash of the pledge card for a
 * user who then lands in control would be exposure that cannot be undone.
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
  if (!inStudyContext) {
    return true;
  }
  if (studyEnabled === undefined) {
    return false;
  }
  if (!studyEnabled) {
    return true;
  }
  return consent === 'accepted' && cohort === 'experimental';
}

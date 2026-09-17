import { describe, expect, it } from 'bun:test';
import { isPledgeTrackerAllowed } from './gate';

const on = {
  inStudyContext: true,
  studyEnabled: true,
  consent: 'accepted' as const,
  cohort: 'manipulation' as const,
};

describe('isPledgeTrackerAllowed', () => {
  describe('the kill switch is the outermost gate', () => {
    it('hides the feature everywhere while the switch is off', () => {
      expect(isPledgeTrackerAllowed({ ...on, studyEnabled: false })).toBe(
        false,
      );
      // Including a context that has nothing to do with the study: the
      // feature only ships inside a study for now, so off means off.
      expect(
        isPledgeTrackerAllowed({
          ...on,
          studyEnabled: false,
          inStudyContext: false,
        }),
      ).toBe(false);
    });

    it('hides the feature while the switch state is still unknown', () => {
      expect(isPledgeTrackerAllowed({ ...on, studyEnabled: undefined })).toBe(
        false,
      );
      expect(
        isPledgeTrackerAllowed({
          ...on,
          studyEnabled: undefined,
          inStudyContext: false,
        }),
      ).toBe(false);
    });
  });

  describe('with the switch on, outside a study context', () => {
    it('is the ordinary product — everyone sees it', () => {
      expect(
        isPledgeTrackerAllowed({
          inStudyContext: false,
          studyEnabled: true,
          consent: undefined,
          cohort: undefined,
        }),
      ).toBe(true);
    });
  });

  describe('with the switch on, inside a study context', () => {
    it('shows the feature to the manipulation arm', () => {
      expect(isPledgeTrackerAllowed(on)).toBe(true);
    });

    it('hides it from control — that is the comparison', () => {
      expect(isPledgeTrackerAllowed({ ...on, cohort: 'control' })).toBe(false);
    });

    it('hides it from anyone who has not consented', () => {
      // Pre-exposure would contaminate a later control assignment.
      expect(
        isPledgeTrackerAllowed({
          ...on,
          consent: undefined,
          cohort: undefined,
        }),
      ).toBe(false);
      expect(isPledgeTrackerAllowed({ ...on, consent: 'declined' })).toBe(
        false,
      );
    });

    it('needs the arm as well as consent, never consent alone', () => {
      expect(isPledgeTrackerAllowed({ ...on, cohort: undefined })).toBe(false);
    });
  });
});

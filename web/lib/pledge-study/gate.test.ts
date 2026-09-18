import { describe, expect, it } from 'bun:test';
import { isPledgeTrackerAllowed } from './gate';

const on = {
  inStudyContext: true,
  studyEnabled: true,
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

    it('shows it to the manipulation arm even after a decline', () => {
      // The arm decides, not the answer: consent governs the questionnaire,
      // and gating exposure on it too left the arm in single digits.
      expect(isPledgeTrackerAllowed({ ...on, cohort: 'manipulation' })).toBe(
        true,
      );
    });

    it('still hides it from control after a decline', () => {
      expect(isPledgeTrackerAllowed({ ...on, cohort: 'control' })).toBe(false);
    });

    it('hides it from anyone who was never asked, who has no arm', () => {
      expect(isPledgeTrackerAllowed({ ...on, cohort: undefined })).toBe(false);
    });
  });
});

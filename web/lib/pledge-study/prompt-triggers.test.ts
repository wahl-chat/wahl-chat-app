import { describe, expect, it } from 'bun:test';
import {
  absoluteFallbackRemainingMs,
  isPromptEligible,
} from './prompt-triggers';
import { ABSOLUTE_FALLBACK_MS, MAX_PROMPTS } from './study-config';

const eligible = {
  consent: 'accepted' as const,
  questionnaireClicked: false,
  promptCount: 0,
  promptShowing: false,
};

describe('isPromptEligible', () => {
  it('asks a consented participant who has not been asked yet', () => {
    expect(isPromptEligible(eligible)).toBe(true);
  });

  it('never asks someone who has not consented', () => {
    expect(isPromptEligible({ ...eligible, consent: undefined })).toBe(false);
    expect(isPromptEligible({ ...eligible, consent: 'declined' })).toBe(false);
  });

  it('stops once the questionnaire has been opened', () => {
    expect(isPromptEligible({ ...eligible, questionnaireClicked: true })).toBe(
      false,
    );
  });

  it('enforces the hard cap', () => {
    expect(
      isPromptEligible({ ...eligible, promptCount: MAX_PROMPTS - 1 }),
    ).toBe(true);
    expect(isPromptEligible({ ...eligible, promptCount: MAX_PROMPTS })).toBe(
      false,
    );
    // The cap is persisted, so a reload can seed a count above it.
    expect(
      isPromptEligible({ ...eligible, promptCount: MAX_PROMPTS + 5 }),
    ).toBe(false);
  });

  it('does not stack a prompt on top of one already showing', () => {
    expect(isPromptEligible({ ...eligible, promptShowing: true })).toBe(false);
  });
});

describe('absoluteFallbackRemainingMs', () => {
  it('waits the full window immediately after the first answer', () => {
    expect(absoluteFallbackRemainingMs(1_000, 1_000)).toBe(
      ABSOLUTE_FALLBACK_MS,
    );
  });

  it('counts down from the stamp, not from when it was asked', () => {
    expect(absoluteFallbackRemainingMs(1_000, 1_000 + 20_000)).toBe(
      ABSOLUTE_FALLBACK_MS - 20_000,
    );
  });

  it('clamps to zero past the deadline so a late reload prompts promptly', () => {
    expect(
      absoluteFallbackRemainingMs(1_000, 1_000 + ABSOLUTE_FALLBACK_MS),
    ).toBe(0);
    expect(absoluteFallbackRemainingMs(1_000, 1_000 + 60 * 60_000)).toBe(0);
  });

  it('is one minute, the agreed safeguard', () => {
    expect(ABSOLUTE_FALLBACK_MS).toBe(60_000);
  });
});

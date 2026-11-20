import { describe, expect, it } from 'bun:test';
import { resultSections } from './result-layout';

describe('resultSections', () => {
  it('shows the score row only once the card is cast', () => {
    const base = { chatEnabled: false, preview: false };
    expect(resultSections({ ...base, cast: false }).scoreRow).toBe(false);
    expect(resultSections({ ...base, cast: true }).scoreRow).toBe(true);
  });

  it('shows the chat card when the switch or the preview is on', () => {
    const chat = (chatEnabled: boolean, preview: boolean) =>
      resultSections({ cast: true, chatEnabled, preview }).chatCard;
    expect(chat(false, false)).toBe(false);
    expect(chat(true, false)).toBe(true);
    expect(chat(false, true)).toBe(true);
  });
});

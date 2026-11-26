import { describe, expect, it } from 'bun:test';
import { resultSections } from './result-layout';

describe('resultSections', () => {
  it('shows the score row only once the card is cast', () => {
    const base = { chatEnabled: false, chatAnswersLive: false, preview: false };
    expect(resultSections({ ...base, cast: false }).scoreRow).toBe(false);
    expect(resultSections({ ...base, cast: true }).scoreRow).toBe(true);
  });

  it('shows the chat card outside preview only when the switch and the answers agree', () => {
    const chat = (
      chatEnabled: boolean,
      chatAnswersLive: boolean,
      preview: boolean,
    ) =>
      resultSections({ cast: true, chatEnabled, chatAnswersLive, preview })
        .chatCard;
    expect(chat(false, false, false)).toBe(false);
    expect(chat(true, false, false)).toBe(false);
    expect(chat(false, true, false)).toBe(false);
    expect(chat(true, true, false)).toBe(true);
  });

  it('shows the chat card in preview whatever the switches say', () => {
    expect(
      resultSections({
        cast: true,
        chatEnabled: false,
        chatAnswersLive: false,
        preview: true,
      }).chatCard,
    ).toBe(true);
  });
});

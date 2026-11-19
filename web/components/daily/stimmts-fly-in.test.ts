import { afterEach, beforeEach, describe, expect, it } from 'bun:test';
import { fade } from './stimmts-fly-in';

type Recorded = { frames: Keyframe[]; options: KeyframeAnimationOptions };

function fakeElement() {
  const calls: Recorded[] = [];
  const element = {
    style: {} as Record<string, string>,
    offsetHeight: 100,
    parentElement: null,
    animate(frames: Keyframe[], options: KeyframeAnimationOptions) {
      calls.push({ frames, options });
      return { finished: Promise.resolve(), cancel() {} };
    },
  };
  return { element: element as unknown as HTMLElement, calls };
}

describe('fade', () => {
  const original = globalThis.getComputedStyle;
  beforeEach(() => {
    globalThis.getComputedStyle = (() => ({
      rowGap: '16px',
    })) as unknown as typeof getComputedStyle;
  });
  afterEach(() => {
    globalThis.getComputedStyle = original;
  });

  it('closes the slot as the card fades, without moving the card', async () => {
    const card = fakeElement();
    const slot = fakeElement();
    const icon = fakeElement();
    await fade(card.element, slot.element, icon.element);

    expect(card.calls).toHaveLength(1);
    for (const frame of card.calls[0].frames) {
      expect(Object.keys(frame)).toEqual(['opacity']);
    }
    expect(slot.calls).toHaveLength(1);
    expect(slot.calls[0].frames).toEqual([
      { height: '100px', marginBottom: '0px' },
      { height: '0px', marginBottom: '-16px' },
    ]);
    expect(icon.calls[0].frames).toEqual([{ opacity: 0 }, { opacity: 1 }]);
  });

  it('works without an icon to fade in', async () => {
    const card = fakeElement();
    const slot = fakeElement();
    expect(await fade(card.element, slot.element, null)).toBeUndefined();
    expect(slot.calls).toHaveLength(1);
  });
});

import { describe, expect, it } from 'bun:test';
import {
  deeperState,
  feedItemKeyOf,
  isPlainClick,
  trailDepth,
} from './feed-trail';

const click = {
  button: 0,
  metaKey: false,
  ctrlKey: false,
  shiftKey: false,
  altKey: false,
};

describe('feed trail', () => {
  it('reads the depth from the entry, zero when there is none', () => {
    expect(trailDepth(null)).toBe(0);
    expect(trailDepth({ __NA: true })).toBe(0);
    expect(trailDepth({ feedDepth: 2 })).toBe(2);
    expect(trailDepth({ feedDepth: 'x' })).toBe(0);
    expect(trailDepth({ feedDepth: -1 })).toBe(0);
  });

  it('goes one level deeper and keeps the rest of the state', () => {
    expect(deeperState({ __NA: true })).toEqual({ __NA: true, feedDepth: 1 });
    expect(deeperState(deeperState(null))).toEqual({ feedDepth: 2 });
  });

  it('reads the item key of a feed link', () => {
    expect(feedItemKeyOf('/?state=bt&item=bundestag_2026-11-13_v6771')).toBe(
      'bundestag_2026-11-13_v6771',
    );
    expect(feedItemKeyOf('/?state=bt')).toBeNull();
  });

  it('leaves modified clicks to the browser', () => {
    expect(isPlainClick(click)).toBe(true);
    for (const key of ['metaKey', 'ctrlKey', 'shiftKey', 'altKey'] as const) {
      expect(isPlainClick({ ...click, [key]: true })).toBe(false);
    }
    expect(isPlainClick({ ...click, button: 1 })).toBe(false);
  });
});

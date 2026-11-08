import { describe, expect, it } from 'bun:test';
import { edgeFadeMask, scrollEdges } from './scroll-edges';

describe('scrollEdges', () => {
  it('has more to the right only at the start', () => {
    expect(scrollEdges(0, 300, 900)).toEqual({ start: false, end: true });
  });

  it('has more on both sides in the middle', () => {
    expect(scrollEdges(300, 300, 900)).toEqual({ start: true, end: true });
  });

  it('has more to the left only at the end, sub-pixel short included', () => {
    expect(scrollEdges(599.5, 300, 900)).toEqual({ start: true, end: false });
  });

  it('has nothing to scroll when everything fits', () => {
    expect(scrollEdges(0, 300, 300)).toEqual({ start: false, end: false });
  });
});

describe('edgeFadeMask', () => {
  it('fades only the sides with more content', () => {
    expect(edgeFadeMask({ start: false, end: true })).toBe(
      'linear-gradient(to right, black 0, black calc(100% - 32px), transparent 100%)',
    );
    expect(edgeFadeMask({ start: true, end: false })).toBe(
      'linear-gradient(to right, transparent 0, black 32px, black 100%)',
    );
  });

  it('is absent when nothing is cut off', () => {
    expect(edgeFadeMask({ start: false, end: false })).toBeUndefined();
  });
});

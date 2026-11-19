import { describe, expect, it } from 'bun:test';
import { PUZZLES } from './content';
import { briefingFront, startMeta } from './start-view';
import type { Puzzle } from './types';

function puzzle(id: string): Puzzle {
  const found = PUZZLES.find((candidate) => candidate.id === id);
  if (!found) {
    throw new Error(`no puzzle ${id}`);
  }
  return found;
}

describe('briefingFront', () => {
  it('shows the three key points when the puzzle has them', () => {
    const front = briefingFront(puzzle('tankrabatt-2026'));
    expect(front.kind).toBe('points');
    if (front.kind !== 'points') return;
    expect(front.points).toHaveLength(3);
    expect(front.points[0].source).toEqual({
      document: '21/8157',
      page: 418,
    });
  });

  it('falls back to the briefing paragraph without key points', () => {
    const withoutPoints = {
      ...puzzle('tankrabatt-2026'),
      keyPoints: undefined,
    };
    expect(briefingFront(withoutPoints)).toEqual({
      kind: 'briefing',
      text: withoutPoints.briefing,
    });
  });
});

describe('startMeta', () => {
  it('names the feed topic and the vote day', () => {
    expect(startMeta(puzzle('tankrabatt-2026'))).toEqual({
      feedTopic: 'climate_environment',
      label: 'Energie · 25. September',
    });
  });
});

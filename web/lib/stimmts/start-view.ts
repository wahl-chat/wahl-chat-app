import { voteDateShort } from './labels';
import { type FeedTopic, feedTopicFor } from './topic';
import type { KeyPoint, Puzzle } from './types';

export type BriefingFront =
  | { kind: 'points'; points: KeyPoint[] }
  | { kind: 'briefing'; text: string };

/**
 * What the front of the briefing card reads: the three sourced key points,
 * or the briefing paragraph for a puzzle that has none yet.
 */
export function briefingFront(puzzle: Puzzle): BriefingFront {
  return puzzle.keyPoints
    ? { kind: 'points', points: puzzle.keyPoints }
    : { kind: 'briefing', text: puzzle.briefing };
}

/** "● Energie · 25. September", the feed's own meta line for a card. */
export function startMeta(puzzle: Puzzle): {
  feedTopic: FeedTopic;
  label: string;
} {
  return {
    // The validator rejects an unmapped topic, so the fallback never shows in
    // shipped content; it only keeps the type honest.
    feedTopic: feedTopicFor(puzzle.topic) ?? 'other',
    label: `${puzzle.topic} · ${voteDateShort(puzzle.voteDate)}`,
  };
}

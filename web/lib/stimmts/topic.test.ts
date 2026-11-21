import { describe, expect, it } from 'bun:test';
import { DAILY_TOPIC_KEYS } from '@/lib/daily/topics';
import puzzlesJson from './content/puzzles.json';
import { FEED_TOPIC_BY_STIMMTS_TOPIC, feedTopicFor } from './topic';

describe('feedTopicFor', () => {
  it('maps a Stimmt’s topic to the feed topic', () => {
    expect(feedTopicFor('Energie')).toBe('climate_environment');
    expect(feedTopicFor('Migration')).toBe('migration_integration');
  });

  it('returns undefined for a topic word with no mapping', () => {
    expect(feedTopicFor('Raumfahrt')).toBeUndefined();
  });

  it('only maps to topics the feed knows', () => {
    for (const feedTopic of Object.values(FEED_TOPIC_BY_STIMMTS_TOPIC)) {
      expect(DAILY_TOPIC_KEYS).toContain(feedTopic);
    }
  });

  it('maps every topic in the shipped puzzles', () => {
    const unmapped = puzzlesJson
      .map((puzzle) => puzzle.topic)
      .filter((topic) => feedTopicFor(topic) === undefined);
    expect(unmapped).toEqual([]);
  });
});

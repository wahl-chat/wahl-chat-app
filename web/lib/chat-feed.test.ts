import { describe, expect, it } from 'bun:test';
import type { DebateFacts, FeedItem } from '@/lib/firebase/firebase.types';
import {
  type FeedPick,
  WEEK_QUESTION,
  feedPicks,
  filterPicks,
  starterQuestions,
} from './chat-feed';

function item(
  id: string,
  date: string,
  rank: number,
  overrides: {
    headline?: string;
    questions?: string[];
    status?: FeedItem['status'];
    heat?: { interjections: number; minutes: number };
  } = {},
): FeedItem {
  return {
    id,
    kind: overrides.heat ? 'debate' : 'vote',
    edition_id: `bundestag_${date}`,
    parliament: 'bundestag',
    parliament_name: 'Bundestag',
    region: 'DE',
    date,
    rank,
    topics: ['health_care'],
    status: overrides.status ?? 'published',
    debate: overrides.heat
      ? ({
          interjections: overrides.heat.interjections,
          debate_minutes: overrides.heat.minutes,
        } as DebateFacts)
      : null,
    vote: null,
    content: {
      de: {
        headline: overrides.headline ?? id,
        teaser: null,
        key_points: [],
        positions: [],
        suggested_questions: overrides.questions ?? [],
        quote_translation: null,
        origin: 'generated',
      },
    },
  };
}

describe('feedPicks', () => {
  it('keeps published items, newest day first, agenda order within', () => {
    const picks = feedPicks([
      item('a', '2026-11-12', 2),
      item('b', '2026-11-13', 1),
      item('c', '2026-11-12', 0),
      item('d', '2026-11-13', 0, { status: 'retracted' }),
    ]);
    expect(picks.map((p) => p.id)).toEqual(['b', 'c', 'a']);
  });

  it('measures heat for debates only', () => {
    const [debate, vote] = feedPicks([
      item('d', '2026-11-13', 0, { heat: { interjections: 30, minutes: 60 } }),
      item('v', '2026-11-13', 1),
    ]);
    expect(debate.heat).toBe(0.5);
    expect(vote.heat).toBeNull();
  });

  it('drops blank questions', () => {
    const [pick] = feedPicks([
      item('a', '2026-11-13', 0, { questions: ['', 'Warum?'] }),
    ]);
    expect(pick.questions).toEqual(['Warum?']);
  });
});

describe('filterPicks', () => {
  const picks = feedPicks([
    item('a', '2026-11-13', 0, { headline: 'Mietpreisbremse verlängert' }),
    item('b', '2026-11-13', 1, { headline: 'Bundeswehr in Litauen' }),
  ]);

  it('matches every term, ignoring case', () => {
    expect(filterPicks(picks, 'MIET verl').map((p) => p.id)).toEqual(['a']);
    expect(filterPicks(picks, 'miet litauen')).toEqual([]);
  });

  it('returns everything for an empty query', () => {
    expect(filterPicks(picks, '  ')).toHaveLength(2);
  });
});

describe('starterQuestions', () => {
  const picks: FeedPick[] = feedPicks([
    item('old', '2026-11-06', 0, { questions: ['Alt?'] }),
    item('calm', '2026-11-13', 0, {
      questions: ['Ruhig?'],
      heat: { interjections: 1, minutes: 60 },
    }),
    item('hot', '2026-11-13', 1, {
      questions: ['Heiß?', 'Noch eine?'],
      heat: { interjections: 60, minutes: 60 },
    }),
    item('vote', '2026-11-13', 2, { questions: ['Abgestimmt?'] }),
    item('silent', '2026-11-13', 3),
    item('more', '2026-11-13', 4, { questions: ['Viertes?'] }),
  ]);

  it("leads with the week question, then the newest day's liveliest items", () => {
    expect(starterQuestions(picks)).toEqual([
      { question: WEEK_QUESTION },
      { question: 'Heiß?', feedItemId: 'hot' },
      { question: 'Ruhig?', feedItemId: 'calm' },
      { question: 'Abgestimmt?', feedItemId: 'vote' },
    ]);
  });

  it("offers an anchored item's own questions", () => {
    expect(starterQuestions(picks, 'hot')).toEqual([
      { question: 'Heiß?', feedItemId: 'hot' },
      { question: 'Noch eine?', feedItemId: 'hot' },
    ]);
  });

  it('falls back to general questions without a feed', () => {
    const questions = starterQuestions([], 'unknown');
    expect(questions[0]).toEqual({ question: WEEK_QUESTION });
    expect(questions.length).toBeGreaterThan(2);
    expect(questions.every((q) => q.feedItemId === undefined)).toBe(true);
  });
});

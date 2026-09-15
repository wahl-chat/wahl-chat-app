import { describe, expect, test } from 'bun:test';
import { buildChatSessionUrl } from './chat-route';
import {
  type LandingComposerState,
  landingComposerReducer,
} from './landing-composer-state';

const draft: LandingComposerState = {
  contextId: 'berlin',
  question: 'Wie werden Mieten bezahlbar?',
  partyIds: ['spd', 'gruene'],
  focusRequest: 0,
};

describe('landing question flow', () => {
  test('changing election preserves the draft but clears election-specific party selection', () => {
    const next = landingComposerReducer(draft, {
      type: 'context',
      contextId: 'mv',
    });
    expect(next.question).toBe(draft.question);
    expect(next.partyIds).toEqual([]);
    expect(next.contextId).toBe('mv');
    expect(
      landingComposerReducer(draft, { type: 'context', contextId: 'berlin' })
        .partyIds,
    ).toEqual(draft.partyIds);
  });

  test('applying parties preserves the question and sends both together', () => {
    const next = landingComposerReducer(draft, {
      type: 'parties',
      partyIds: ['cdu', 'spd'],
    });
    const url = new URL(
      buildChatSessionUrl({
        contextId: next.contextId,
        question: next.question,
        partyIds: next.partyIds,
      }),
      'http://localhost',
    );
    expect(url.searchParams.get('q')).toBe(draft.question);
    expect(url.searchParams.getAll('party_id')).toEqual(['cdu', 'spd']);
  });

  test('a question idea changes scope and requests focus without submitting', () => {
    const next = landingComposerReducer(draft, {
      type: 'suggestion',
      contextId: 'mv',
      question: 'Wie fördert ihr Windkraft?',
    });
    expect(next).toEqual({
      contextId: 'mv',
      question: 'Wie fördert ihr Windkraft?',
      partyIds: [],
      focusRequest: 1,
    });
    const again = landingComposerReducer(next, {
      type: 'suggestion',
      contextId: 'mv',
      question: next.question,
    });
    expect(again.focusRequest).toBe(2);
  });

  test('an idea from the same election keeps the chosen parties', () => {
    expect(
      landingComposerReducer(draft, {
        type: 'suggestion',
        contextId: 'berlin',
        question: 'Wie verbessert ihr Schulen?',
      }).partyIds,
    ).toEqual(draft.partyIds);
  });
});

import { describe, expect, test } from 'bun:test';
import { buildChatSessionUrl } from './chat-route';

describe('buildChatSessionUrl', () => {
  test('keeps a question with query syntax in one q parameter', () => {
    const url = buildChatSessionUrl({
      contextId: 'mv2026',
      question: 'Was gilt für Miete & Energie?',
    });
    const parsed = new URL(url, 'https://wahl.chat');

    expect(parsed.pathname).toBe('/mv2026/session');
    expect(parsed.searchParams.get('q')).toBe('Was gilt für Miete & Energie?');
    expect([...parsed.searchParams.keys()]).toEqual(['q']);
  });

  test('preserves every selected party as a repeated parameter', () => {
    const url = buildChatSessionUrl({
      contextId: 'berlin2026',
      partyIds: ['spd', 'cdu'],
    });
    const parsed = new URL(url, 'https://wahl.chat');

    expect(parsed.searchParams.getAll('party_id')).toEqual(['spd', 'cdu']);
  });

  test('does not add an empty query string', () => {
    expect(buildChatSessionUrl({ contextId: 'mv2026' })).toBe(
      '/mv2026/session',
    );
  });
});

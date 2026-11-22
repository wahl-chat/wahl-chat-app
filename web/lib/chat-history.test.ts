import { describe, expect, it } from 'bun:test';
import { generalChatHref, sessionHref } from '@/lib/chat-history';
import { DEFAULT_CONTEXT_ID, GENERAL_CONTEXT_ID } from '@/lib/constants';
import type { ChatSession } from '@/lib/firebase/firebase.types';

const session = (id: string, context_id?: string): ChatSession => ({
  id,
  user_id: 'u',
  context_id,
});

describe('sessionHref', () => {
  it('falls back to the default context for legacy sessions', () => {
    expect(sessionHref(session('s1'))).toBe(
      `/${DEFAULT_CONTEXT_ID}/session/s1`,
    );
  });
});

describe('generalChatHref', () => {
  it('returns the newest general session', () => {
    const history = [
      session('election', 'abgeordnetenhauswahl-berlin-2026'),
      session('newest', GENERAL_CONTEXT_ID),
      session('older', GENERAL_CONTEXT_ID),
    ];
    expect(generalChatHref(history)).toBe(
      `/${GENERAL_CONTEXT_ID}/session/newest`,
    );
  });

  it('starts a new general chat without one', () => {
    expect(generalChatHref([session('e', 'landtagswahl-x')])).toBe('/chat');
  });
});

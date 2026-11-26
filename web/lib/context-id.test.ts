import { describe, expect, it } from 'bun:test';
import { looksLikeContextId } from '@/lib/context-id';
import prodContexts from '../../firebase/firestore_data/prod/contexts.json';

describe('looksLikeContextId', () => {
  // A miss here 404s a stale link to a real election instead of redirecting it.
  // General contexts are served under their own route (/chat), not as an
  // election link.
  it('accepts every election context id in production', () => {
    const ids = Object.entries(prodContexts)
      .filter(([, context]) => context.type !== 'general')
      .map(([id]) => id);
    expect(ids.length).toBeGreaterThan(0);

    for (const id of ids) {
      expect(looksLikeContextId(id)).toBe(true);
    }
  });

  it('accepts the compact form', () => {
    expect(looksLikeContextId('bw2026')).toBe(true);
  });

  it('rejects paths that were never an election', () => {
    for (const segment of ['news', 'feed', 'bundestag', 'foo', 'aktuell']) {
      expect(looksLikeContextId(segment)).toBe(false);
    }
  });
});

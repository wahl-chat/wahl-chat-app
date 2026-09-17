import { describe, expect, it } from 'bun:test';
import { parsePageVisitFlushBody } from './page-visit-request';

const VISIT_ID = '2c1d8f3a-4b5e-4c6d-8e9f-0a1b2c3d4e5f';

describe('parsePageVisitFlushBody', () => {
  it('accepts a well-formed payload', () => {
    const parsed = parsePageVisitFlushBody({
      visit_id: VISIT_ID,
      visible_ms: 1500.4,
      last_path: '/landtagswahl-sachsen-anhalt-2026',
      context_id: 'landtagswahl-sachsen-anhalt-2026',
    });
    expect(parsed.ok).toBe(true);
    if (parsed.ok) {
      expect(parsed.data.visibleMs).toBe(1500);
      expect(parsed.data.contextId).toBe('landtagswahl-sachsen-anhalt-2026');
    }
  });

  it('rejects a missing or malformed visit id', () => {
    expect(parsePageVisitFlushBody({ visible_ms: 10 }).ok).toBe(false);
    expect(
      parsePageVisitFlushBody({ visit_id: 'not-a-uuid', visible_ms: 10 }).ok,
    ).toBe(false);
  });

  it('rejects non-numeric visible_ms', () => {
    expect(
      parsePageVisitFlushBody({ visit_id: VISIT_ID, visible_ms: '12' }).ok,
    ).toBe(false);
  });

  it('keeps a Firebase-sized id token', () => {
    const idToken = `header.${'a'.repeat(900)}.signature`;
    const parsed = parsePageVisitFlushBody({
      visit_id: VISIT_ID,
      visible_ms: 10,
      id_token: idToken,
    });
    expect(parsed.ok).toBe(true);
    if (parsed.ok) {
      expect(parsed.data.idToken).toBe(idToken);
    }
  });
});

import { afterEach, describe, expect, setSystemTime, test } from 'bun:test';
import { NextRequest } from 'next/server';
import {
  CONTEXT_ELECTION_DATES,
  DEFAULT_CONTEXT_ID,
  REGION_TO_CONTEXT,
} from './lib/constants';
import { middleware } from './middleware';

afterEach(() => setSystemTime());

describe('geo routing', () => {
  test('falls back for past elections and keeps upcoming regional contexts', async () => {
    setSystemTime(new Date('2026-08-21T00:00:00Z'));

    for (const [region, contextId] of Object.entries(REGION_TO_CONTEXT)) {
      expect(CONTEXT_ELECTION_DATES[contextId]).toBeDefined();
      const request = new NextRequest('https://wahl.chat/', {
        headers: {
          'x-vercel-ip-country': 'DE',
          'x-vercel-ip-country-region': region,
        },
      });
      const response = await middleware(request);
      const isPast =
        new Date(CONTEXT_ELECTION_DATES[contextId]).getTime() <
        Date.now() - 5 * 24 * 60 * 60 * 1000;
      const expectedContext = isPast ? DEFAULT_CONTEXT_ID : contextId;

      expect(response.headers.get('location')).toBe(
        `https://wahl.chat/${expectedContext}`,
      );
    }
  });
});

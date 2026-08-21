import {
  afterEach,
  describe,
  expect,
  setSystemTime,
  spyOn,
  test,
} from 'bun:test';
import { NextRequest } from 'next/server';
import { DEFAULT_CONTEXT_ID, REGION_CONTEXTS } from './lib/constants';
import { middleware } from './middleware';

afterEach(() => setSystemTime());

describe('geo routing', () => {
  test('logs preview geo-routing decisions with the Vercel client IP', async () => {
    const vercelEnv = process.env.VERCEL_ENV;
    const info = spyOn(console, 'info').mockImplementation(() => {});
    process.env.VERCEL_ENV = 'preview';

    try {
      const request = new NextRequest('https://wahl.chat/', {
        headers: {
          'x-vercel-forwarded-for': '203.0.113.42',
          'x-vercel-ip-country': 'DE',
          'x-vercel-ip-country-region': 'BE',
        },
      });

      await middleware(request);

      expect(info.mock.calls).toEqual([
        [
          '[DEBUG-geo-routing]',
          {
            ip: '203.0.113.42',
            country: 'DE',
            region: 'BE',
            contextId: 'abgeordnetenhauswahl-berlin-2026',
          },
        ],
      ]);
    } finally {
      info.mockRestore();
      if (vercelEnv === undefined) delete process.env.VERCEL_ENV;
      else process.env.VERCEL_ENV = vercelEnv;
    }
  });

  test('falls back for past elections and keeps upcoming regional contexts', async () => {
    setSystemTime(new Date('2026-08-21T00:00:00Z'));

    for (const [region, context] of Object.entries(REGION_CONTEXTS)) {
      const request = new NextRequest('https://wahl.chat/', {
        headers: {
          'x-vercel-ip-country': 'DE',
          'x-vercel-ip-country-region': region,
        },
      });
      const response = await middleware(request);
      const isPast =
        new Date(context.electionDate).getTime() <
        Date.now() - 5 * 24 * 60 * 60 * 1000;
      const expectedContext = isPast ? DEFAULT_CONTEXT_ID : context.contextId;

      expect(response.headers.get('location')).toBe(
        `https://wahl.chat/${expectedContext}`,
      );
    }
  });
});

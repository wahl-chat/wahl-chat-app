import { afterEach, describe, expect, setSystemTime, test } from 'bun:test';
import { NextRequest } from 'next/server';
import { DEFAULT_CONTEXT_ID, REGION_CONTEXTS } from './lib/constants';
import { middleware } from './middleware';

afterEach(() => setSystemTime());

function requestFrom(url, region) {
  return new NextRequest(url, {
    headers: region
      ? {
          'x-vercel-ip-country': 'DE',
          'x-vercel-ip-country-region': region,
        }
      : {},
  });
}

describe('geo routing', () => {
  // Legacy links name no election of their own, so the region picks one. They
  // are the only requests allowed to vary by requester.
  test('falls back for past elections and keeps upcoming regional contexts', async () => {
    setSystemTime(new Date('2026-08-21T00:00:00Z'));

    for (const [region, context] of Object.entries(REGION_CONTEXTS)) {
      const response = await middleware(
        requestFrom('https://wahl.chat/sources', region),
      );
      const isPast =
        new Date(context.electionDate).getTime() <
        Date.now() - 5 * 24 * 60 * 60 * 1000;
      const expectedContext = isPast ? DEFAULT_CONTEXT_ID : context.contextId;

      expect(response.headers.get('location')).toBe(
        `https://wahl.chat/${expectedContext}/sources`,
      );
    }
  });

  test('an unmapped region falls back to the default election', async () => {
    const response = await middleware(
      requestFrom('https://wahl.chat/sources', 'HH'),
    );

    expect(response.headers.get('location')).toBe(
      `https://wahl.chat/${DEFAULT_CONTEXT_ID}/sources`,
    );
  });
});

describe('the landing page', () => {
  // / holds the site's inbound links. Redirecting it sent crawlers and German
  // visitors to different elections and pointed every backlink at a redirect
  // instead of a page, so it must return content for everyone alike.
  test('is never redirected, whatever the request says about its origin', async () => {
    setSystemTime(new Date('2026-08-21T00:00:00Z'));

    for (const region of [undefined, ...Object.keys(REGION_CONTEXTS)]) {
      const response = await middleware(
        requestFrom('https://wahl.chat/', region),
      );

      expect(response.headers.get('location')).toBeNull();
    }
  });
});

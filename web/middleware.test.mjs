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

describe('legacy context-less URLs', () => {
  test('bare paths land permanently on /, so their link equity consolidates', async () => {
    for (const path of ['/chat', '/session']) {
      const response = await middleware(
        requestFrom(`https://wahl.chat${path}`),
      );

      expect(response.headers.get('location')).toBe('https://wahl.chat/');
      expect(response.status).toBe(308);
    }
  });

  test('paths carrying a party or session keep a context, temporarily', async () => {
    const party = await middleware(requestFrom('https://wahl.chat/chat/spd'));
    expect(party.headers.get('location')).toBe(
      `https://wahl.chat/${DEFAULT_CONTEXT_ID}/session?party_id=spd`,
    );
    expect(party.status).toBe(307);

    const session = await middleware(
      requestFrom('https://wahl.chat/session/abc'),
    );
    expect(session.headers.get('location')).toBe(
      `https://wahl.chat/${DEFAULT_CONTEXT_ID}/session/abc`,
    );
  });

  test('a path merely starting with the same letters is not a legacy /chat URL', async () => {
    const response = await middleware(requestFrom('https://wahl.chat/chatfoo'));

    expect(response.headers.get('location')).toBeNull();
  });
});

describe('the budget kill switch', () => {
  afterEach(() => {
    delete process.env.BUDGET_SPENT;
  });

  test('sends the site to /budget-spent without redirecting it to itself', async () => {
    process.env.BUDGET_SPENT = 'true';

    const landing = await middleware(requestFrom('https://wahl.chat/'));
    expect(landing.headers.get('location')).toBe(
      'https://wahl.chat/budget-spent',
    );

    // /budget-spent is itself a static page: redirecting it here would loop.
    const killSwitchPage = await middleware(
      requestFrom('https://wahl.chat/budget-spent'),
    );
    expect(killSwitchPage.headers.get('location')).toBeNull();
  });

  test('never diverts the metadata routes', async () => {
    process.env.BUDGET_SPENT = 'true';

    for (const path of ['/sitemap.xml', '/robots.txt', '/manifest.json']) {
      const response = await middleware(
        requestFrom(`https://wahl.chat${path}`),
      );

      expect(response.headers.get('location')).toBeNull();
    }
  });
});

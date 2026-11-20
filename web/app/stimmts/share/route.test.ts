import { describe, expect, mock, test } from 'bun:test';

// The image draws without custom fonts, so no test reaches the network.
mock.module('@/lib/og/google-font', () => ({
  loadGoogleFont: () => Promise.reject(new Error('offline')),
}));

const { GET } = await import('./route');

const BASE =
  'http://localhost:3000/stimmts/share?f=square&n=1&s=3&d=2026-11-15';
const request = (query = '') => GET(new Request(`${BASE}${query}`));

describe('share image route: style parameter', () => {
  test('an unknown style redirects to the canonical URL without it', async () => {
    const response = await request('&t=GOLD');
    expect(response.status).toBe(308);
    expect(response.headers.get('location')).toBe(BASE);
  });

  test('with several styles the first counts', async () => {
    const response = await request('&t=nacht&t=gold');
    expect(response.status).toBe(308);
    expect(response.headers.get('location')).toBe(`${BASE}&t=nacht`);
  });

  test('a valid style draws a PNG', async () => {
    const response = await request('&t=nacht');
    expect(response.status).toBe(200);
    expect(response.headers.get('content-type')).toBe('image/png');
  });
});

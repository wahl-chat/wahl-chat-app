import {
  afterEach,
  beforeEach,
  describe,
  expect,
  mock,
  spyOn,
  test,
} from 'bun:test';

// No test reaches the network: each font loads, or fails, as the test says.
const failing = new Set<string>();
const requested: string[] = [];
mock.module('@/lib/og/google-font', () => ({
  loadGoogleFont: (spec: string) => {
    const family = spec.split(':')[0];
    requested.push(family);
    return failing.has(family)
      ? Promise.reject(new Error('offline'))
      : Promise.resolve(new ArrayBuffer(8));
  },
}));

type Route = typeof import('./route');

// The route keeps what it loaded for the life of the instance, so each test
// imports a fresh copy.
let copy = 0;
async function freshRoute(): Promise<Route> {
  copy += 1;
  return import(`./route?copy=${copy}`);
}

const BASE =
  'http://localhost:3000/stimmts/share?f=square&n=1&s=3&d=2026-11-15';
const request = (route: Route, query = '') =>
  route.GET(new Request(`${BASE}${query}`));

// A failed font load is logged on purpose; these tests provoke it and keep the
// output clean.
beforeEach(() => {
  spyOn(console, 'error').mockImplementation(() => {});
});
afterEach(() => {
  failing.clear();
  requested.length = 0;
  mock.restore();
});

describe('share image route: style parameter', () => {
  test('an unknown style redirects to the canonical URL without it', async () => {
    const response = await request(await freshRoute(), '&t=GOLD');
    expect(response.status).toBe(308);
    expect(response.headers.get('location')).toBe(BASE);
  });

  test('with several styles the first counts', async () => {
    const response = await request(await freshRoute(), '&t=nacht&t=gold');
    expect(response.status).toBe(308);
    expect(response.headers.get('location')).toBe(`${BASE}&t=nacht`);
  });

  test('a valid style draws a PNG', async () => {
    const response = await request(await freshRoute(), '&t=nacht');
    expect(response.status).toBe(200);
    expect(response.headers.get('content-type')).toBe('image/png');
  });
});

describe('share image route: fonts', () => {
  test('without the base fonts the image is not cached', async () => {
    failing.add('Arimo');
    const response = await request(await freshRoute());
    expect(response.status).toBe(200);
    expect(response.headers.get('cache-control')).toBe('no-store');
  });

  test('only a Papier image loads the serif font', async () => {
    const route = await freshRoute();
    await request(route, '&t=nacht');
    expect(requested).not.toContain('Tinos');
    await request(route);
    expect(requested).not.toContain('Tinos');
    await request(route, '&t=papier');
    expect(requested).toContain('Tinos');
  });

  test('a Papier image without its serif font is not cached', async () => {
    failing.add('Tinos');
    const response = await request(await freshRoute(), '&t=papier');
    expect(response.status).toBe(200);
    expect(response.headers.get('content-type')).toBe('image/png');
    expect(response.headers.get('cache-control')).toBe('no-store');
  });

  test('a failed serif font does not affect the other styles', async () => {
    failing.add('Tinos');
    const response = await request(await freshRoute(), '&t=nacht');
    expect(response.headers.get('cache-control')).not.toBe('no-store');
  });
});

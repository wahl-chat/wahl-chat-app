import { describe, expect, it } from 'bun:test';
import { JUST_PLAYED_KEY, PRESENCE_SCRIPT, presenceOf } from './presence';
import { STORAGE_KEY } from './progress-store';

const today = '2026-11-15';

function saved(...finishedOn: (string | null)[]): string {
  return JSON.stringify({
    version: 1,
    games: Object.fromEntries(
      finishedOn.map((date, index) => [
        `p${index}`,
        { guesses: {}, finishedOn: date, cast: false },
      ]),
    ),
  });
}

describe('presenceOf', () => {
  it('is null without a save or with junk', () => {
    expect(presenceOf(null, today)).toBeNull();
    expect(presenceOf('{nope', today)).toBeNull();
    expect(presenceOf('42', today)).toBeNull();
    expect(presenceOf('{"version":2,"games":{}}', today)).toBeNull();
    expect(presenceOf('{"version":1,"games":{"a":null}}', today)).toBeNull();
  });

  it('reads today, before and unfinished', () => {
    expect(presenceOf(saved('2026-11-14', today), today)).toBe('today');
    expect(presenceOf(saved('2026-11-13', '2026-11-14'), today)).toBe('before');
    expect(presenceOf(saved(null, null), today)).toBeNull();
  });
});

function run(
  local: (key: string) => string | null,
  session: string | null,
): Record<string, string> {
  const dataset: Record<string, string> = {};
  new Function('document', 'localStorage', 'sessionStorage', PRESENCE_SCRIPT)(
    { documentElement: { dataset } },
    { getItem: local },
    { getItem: (key: string) => (key === JUST_PLAYED_KEY ? session : null) },
  );
  return dataset;
}

describe('PRESENCE_SCRIPT', () => {
  const berlinToday = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Berlin',
  }).format(new Date());

  it('marks the page and the fly flag', () => {
    const dataset = run(() => saved(berlinToday), berlinToday);
    expect(dataset.stimmts).toBe('today');
    expect(dataset.stimmtsFly).toBe('');
  });

  it('sets no fly flag for another day and nothing without a save', () => {
    expect(run(() => null, '2020-01-01')).toEqual({});
  });

  it('reads the progress key', () => {
    let asked = '';
    run((key) => {
      asked = key;
      return null;
    }, null);
    expect(asked).toBe(STORAGE_KEY);
  });

  it('leaves the page alone when storage throws', () => {
    const dataset = run(() => {
      throw new Error('blocked');
    }, null);
    expect(dataset).toEqual({});
  });
});

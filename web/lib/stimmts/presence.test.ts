import { describe, expect, it } from 'bun:test';
import {
  JUST_PLAYED_KEY,
  PRESENCE_SCRIPT,
  clearJustPlayed,
  markJustPlayed,
  presenceOf,
} from './presence';
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

describe('markJustPlayed / clearJustPlayed', () => {
  function fakes() {
    const values = new Map<string, string>();
    const session = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => {
        values.set(key, value);
      },
      removeItem: (key: string) => {
        values.delete(key);
      },
    };
    const root = { dataset: {} as Record<string, string | undefined> };
    return { values, session, root };
  }

  it('flags the day and marks <html> for a page reached without a reload', () => {
    const { values, session, root } = fakes();
    markJustPlayed(today, session, root);
    expect(values.get(JUST_PLAYED_KEY)).toBe(today);
    expect(root.dataset).toEqual({ stimmts: 'today', stimmtsFly: '' });
  });

  it('clears the flag and the mark, so the flight never plays twice', () => {
    const { values, session, root } = fakes();
    markJustPlayed(today, session, root);
    clearJustPlayed(session, root);
    expect(values.has(JUST_PLAYED_KEY)).toBe(false);
    expect('stimmtsFly' in root.dataset).toBe(false);
    expect(root.dataset.stimmts).toBe('today');
  });

  it('survives blocked or missing storage', () => {
    const { root } = fakes();
    const blocked = {
      getItem: () => {
        throw new Error('blocked');
      },
      setItem: () => {
        throw new Error('blocked');
      },
      removeItem: () => {
        throw new Error('blocked');
      },
    };
    expect(() => markJustPlayed(today, blocked, root)).not.toThrow();
    expect(root.dataset.stimmts).toBe('today');
    expect(() => clearJustPlayed(blocked, root)).not.toThrow();
    expect(() => markJustPlayed(today, null, root)).not.toThrow();
  });
});

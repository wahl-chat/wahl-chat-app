import { describe, expect, it } from 'bun:test';
import {
  ENTRY_MARKER_KEY,
  ENTRY_MARKER_MAX_AGE_MS,
  chatAskedProps,
  markEntry,
  resolveEntry,
  retentionProps,
} from './analytics-props';
import { EMPTY_PROGRESS, type Progress } from './progress';

function progressWith(games: Record<string, string | null>): Progress {
  return {
    ...EMPTY_PROGRESS,
    games: Object.fromEntries(
      Object.entries(games).map(([id, finishedOn]) => [
        id,
        { guesses: {}, finishedOn, cast: false },
      ]),
    ),
  };
}

describe('retentionProps', () => {
  it('is a first game on a device with nothing saved', () => {
    expect(retentionProps(EMPTY_PROGRESS, 'p1', '2026-11-20')).toEqual({
      games_before: 0,
      played_yesterday: false,
    });
  });

  it('counts the finished games before this one', () => {
    const progress = progressWith({ a: '2026-11-10', b: '2026-11-12' });
    expect(retentionProps(progress, 'p1', '2026-11-20').games_before).toBe(2);
  });

  it('does not count a game that is still open', () => {
    const progress = progressWith({ a: '2026-11-10', b: null });
    expect(retentionProps(progress, 'p1', '2026-11-20').games_before).toBe(1);
  });

  it('leaves out the current puzzle, finished or not', () => {
    const progress = progressWith({ p1: '2026-11-20', a: '2026-11-19' });
    expect(retentionProps(progress, 'p1', '2026-11-20')).toEqual({
      games_before: 1,
      played_yesterday: true,
    });
  });

  it('does not take the current puzzle finished today for yesterday', () => {
    const progress = progressWith({ p1: '2026-11-20' });
    expect(retentionProps(progress, 'p1', '2026-11-20').played_yesterday).toBe(
      false,
    );
  });

  it('tells yesterday from two days ago', () => {
    expect(
      retentionProps(progressWith({ a: '2026-11-19' }), 'p1', '2026-11-20')
        .played_yesterday,
    ).toBe(true);
    expect(
      retentionProps(progressWith({ a: '2026-11-18' }), 'p1', '2026-11-20')
        .played_yesterday,
    ).toBe(false);
  });

  it('finds yesterday across a month boundary', () => {
    expect(
      retentionProps(progressWith({ a: '2026-10-31' }), 'p1', '2026-11-01')
        .played_yesterday,
    ).toBe(true);
    expect(
      retentionProps(progressWith({ a: '2026-02-28' }), 'p1', '2026-03-01')
        .played_yesterday,
    ).toBe(true);
  });
});

function memoryStorage(initial: Record<string, string> = {}) {
  const data = { ...initial };
  return {
    data,
    getItem: (key: string) => data[key] ?? null,
    setItem: (key: string, value: string) => {
      data[key] = value;
    },
    removeItem: (key: string) => {
      delete data[key];
    },
  };
}

const throwing = {
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

describe('resolveEntry', () => {
  const now = 1_000_000_000;

  it('is direct with no marker', () => {
    const storage = memoryStorage();
    expect(resolveEntry({ sharedLink: false, storage, now })).toBe('direct');
  });

  it('reads the marker and clears it', () => {
    const storage = memoryStorage();
    markEntry('feed_card', storage, now - 1000);
    expect(resolveEntry({ sharedLink: false, storage, now })).toBe('feed_card');
    expect(storage.data[ENTRY_MARKER_KEY]).toBeUndefined();
    expect(resolveEntry({ sharedLink: false, storage, now })).toBe('direct');
  });

  it('reads the header icon marker', () => {
    const storage = memoryStorage();
    markEntry('header_icon', storage, now);
    expect(resolveEntry({ sharedLink: false, storage, now })).toBe(
      'header_icon',
    );
  });

  it('puts a shared link before a marker, and still clears the marker', () => {
    const storage = memoryStorage();
    markEntry('feed_card', storage, now);
    expect(resolveEntry({ sharedLink: true, storage, now })).toBe(
      'shared_link',
    );
    expect(storage.data[ENTRY_MARKER_KEY]).toBeUndefined();
  });

  it('counts a stale marker as direct', () => {
    const storage = memoryStorage();
    markEntry('feed_card', storage, now - ENTRY_MARKER_MAX_AGE_MS - 1);
    expect(resolveEntry({ sharedLink: false, storage, now })).toBe('direct');
  });

  it('counts a marker from the future or a garbled one as direct', () => {
    const resolve = (value: string) =>
      resolveEntry({
        sharedLink: false,
        storage: memoryStorage({ [ENTRY_MARKER_KEY]: value }),
        now,
      });
    expect(resolve(`feed_card:${now + 5}`)).toBe('direct');
    expect(resolve('nonsense')).toBe('direct');
    expect(resolve(`other:${now}`)).toBe('direct');
  });

  it('is direct, not an error, when storage throws or is missing', () => {
    expect(resolveEntry({ sharedLink: false, storage: throwing, now })).toBe(
      'direct',
    );
    expect(resolveEntry({ sharedLink: true, storage: throwing, now })).toBe(
      'shared_link',
    );
    expect(resolveEntry({ sharedLink: false, storage: null, now })).toBe(
      'direct',
    );
    expect(() => markEntry('feed_card', throwing, now)).not.toThrow();
  });
});

describe('chatAskedProps', () => {
  it('names the chip, not its text', () => {
    expect(chatAskedProps({ chip: 'in_force' }, 4)).toEqual({
      kind: 'chip',
      chip: 'in_force',
      day: 4,
    });
  });

  it('carries no text for a typed question', () => {
    const props = chatAskedProps({ chip: null }, 4);
    expect(props).toEqual({ kind: 'typed', chip: null, day: 4 });
    expect(Object.keys(props).sort()).toEqual(['chip', 'day', 'kind']);
  });
});

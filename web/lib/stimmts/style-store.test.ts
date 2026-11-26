import { describe, expect, it } from 'bun:test';
import type { StorageLike } from './progress-store';
import { SEEN_KEY, STYLE_KEY, createStyleStore } from './style-store';

function fakeStorage(initial: Record<string, string> = {}) {
  const data = { ...initial };
  const storage: StorageLike = {
    getItem: (key) => data[key] ?? null,
    setItem: (key, value) => {
      data[key] = value;
    },
  };
  return { storage, data };
}

describe('style store', () => {
  it('choose persists', () => {
    const { storage, data } = fakeStorage();
    const store = createStyleStore(storage);
    store.getState().hydrate();
    store.getState().choose('gold');
    expect(store.getState().chosen).toBe('gold');
    expect(data[STYLE_KEY]).toBe('gold');
    const again = createStyleStore(storage);
    again.getState().hydrate();
    expect(again.getState().chosen).toBe('gold');
  });

  it('markSeen persists and merges', () => {
    const { storage, data } = fakeStorage();
    const store = createStyleStore(storage);
    store.getState().hydrate();
    store.getState().markSeen(['papier']);
    store.getState().markSeen(['papier', 'nacht']);
    expect(store.getState().seen).toEqual(['papier', 'nacht']);
    expect(JSON.parse(data[SEEN_KEY])).toEqual(['papier', 'nacht']);
  });

  it('a storage that throws keeps the choice in memory', () => {
    const storage: StorageLike = {
      getItem: () => {
        throw new Error('blocked');
      },
      setItem: () => {
        throw new Error('blocked');
      },
    };
    const store = createStyleStore(storage);
    store.getState().hydrate();
    store.getState().choose('nacht');
    store.getState().markSeen(['nacht']);
    expect(store.getState().chosen).toBe('nacht');
    expect(store.getState().seen).toEqual(['nacht']);
  });

  it('a tampered saved value hydrates as standard', () => {
    const { storage } = fakeStorage({
      [STYLE_KEY]: '../x',
      [SEEN_KEY]: '["bogus","papier",7]',
    });
    const store = createStyleStore(storage);
    store.getState().hydrate();
    expect(store.getState().chosen).toBe('standard');
    expect(store.getState().seen).toEqual(['papier']);
  });
});

import { describe, expect, it } from 'bun:test';
import { PUZZLES } from './content';
import { getGame } from './progress';
import {
  STORAGE_KEY,
  type StorageLike,
  createProgressStore,
} from './progress-store';

const puzzle = PUZZLES[0];
const TODAY = '2026-11-01';

// An in-memory stand-in for localStorage, so the tests need no browser.
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

describe('createProgressStore', () => {
  it('starts empty and unhydrated, then loads what was saved', () => {
    const { storage } = fakeStorage();
    const first = createProgressStore(storage);
    expect(first.getState().hydrated).toBe(false);

    first.getState().hydrate();
    first.getState().answer(puzzle, 'linke', 'no', TODAY);

    // A new store on the same storage is a page reload.
    const reloaded = createProgressStore(storage);
    expect(reloaded.getState().progress.games).toEqual({});
    reloaded.getState().hydrate();
    expect(getGame(reloaded.getState().progress, puzzle.id).guesses).toEqual({
      linke: 'no',
    });
    expect(reloaded.getState().hydrated).toBe(true);
  });

  it('saves the moment an answer is given', () => {
    const { storage, data } = fakeStorage();
    const store = createProgressStore(storage);
    store.getState().hydrate();
    store.getState().answer(puzzle, 'linke', 'no', TODAY);
    expect(JSON.parse(data[STORAGE_KEY]).games[puzzle.id].guesses).toEqual({
      linke: 'no',
    });
  });

  it('does not overwrite saved progress when answered before hydrating', () => {
    const { storage } = fakeStorage();
    const early = createProgressStore(storage);
    early.getState().answer(puzzle, 'linke', 'no', TODAY);

    const later = createProgressStore(storage);
    later.getState().answer(puzzle, 'spd', 'yes', TODAY);
    expect(getGame(later.getState().progress, puzzle.id).guesses).toEqual({
      linke: 'no',
      spd: 'yes',
    });
  });

  it('keeps answers final across a reload', () => {
    const { storage } = fakeStorage();
    const store = createProgressStore(storage);
    store.getState().answer(puzzle, 'linke', 'no', TODAY);

    const reloaded = createProgressStore(storage);
    reloaded.getState().answer(puzzle, 'linke', 'yes', TODAY);
    expect(getGame(reloaded.getState().progress, puzzle.id).guesses.linke).toBe(
      'no',
    );
  });

  it('starts fresh instead of crashing on corrupt saved data', () => {
    const { storage } = fakeStorage({ [STORAGE_KEY]: '{not json' });
    const store = createProgressStore(storage);
    store.getState().hydrate();
    expect(store.getState().progress.games).toEqual({});
    expect(store.getState().hydrated).toBe(true);
  });

  it('still works in memory when there is no storage at all', () => {
    const store = createProgressStore(null);
    store.getState().answer(puzzle, 'linke', 'no', TODAY);
    expect(getGame(store.getState().progress, puzzle.id).guesses.linke).toBe(
      'no',
    );
  });

  it('survives storage that refuses to write', () => {
    const storage: StorageLike = {
      getItem: () => null,
      setItem: () => {
        throw new Error('QuotaExceededError');
      },
    };
    const store = createProgressStore(storage);
    expect(() =>
      store.getState().answer(puzzle, 'linke', 'no', TODAY),
    ).not.toThrow();
    expect(getGame(store.getState().progress, puzzle.id).guesses.linke).toBe(
      'no',
    );
  });
});

describe('the streak across days', () => {
  const PARTIES = ['linke', 'spd', 'gruene', 'cdu', 'afd'];
  const finish = (
    store: ReturnType<typeof createProgressStore>,
    index: number,
    day: string,
  ) => {
    for (const partyId of PARTIES) {
      store.getState().answer(PUZZLES[index], partyId, 'yes', day);
    }
  };

  it('grows from one day to the next, even across a reload', () => {
    const { storage } = fakeStorage();
    finish(createProgressStore(storage), 0, '2026-11-01');

    const reloaded = createProgressStore(storage); // a new page load
    finish(reloaded, 1, '2026-11-02');
    expect(reloaded.getState().progress.streak).toEqual({
      current: 2,
      best: 2,
      lastPlayed: '2026-11-02',
    });
  });

  it('survives resetting one puzzle, which is how a preview replays a day', () => {
    const { storage } = fakeStorage();
    const store = createProgressStore(storage);
    finish(store, 0, '2026-11-01');
    finish(store, 1, '2026-11-02');

    store.getState().resetGame(PUZZLES[1].id);
    const reloaded = createProgressStore(storage);
    reloaded.getState().hydrate();
    expect(
      getGame(reloaded.getState().progress, PUZZLES[1].id).guesses,
    ).toEqual({});
    expect(reloaded.getState().progress.streak.current).toBe(2);

    finish(reloaded, 1, '2026-11-02');
    expect(reloaded.getState().progress.streak.current).toBe(2);
  });
});

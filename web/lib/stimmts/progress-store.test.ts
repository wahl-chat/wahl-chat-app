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

describe('casting the Stimmkarte', () => {
  const finish = (store: ReturnType<typeof createProgressStore>) => {
    for (const party of puzzle.parties) {
      store.getState().answer(puzzle, party.partyId, 'yes', TODAY);
    }
  };

  it('keeps the card in the urn across a reload', () => {
    const { storage } = fakeStorage();
    const store = createProgressStore(storage);
    finish(store);
    store.getState().cast(puzzle.id);

    const reloaded = createProgressStore(storage);
    reloaded.getState().hydrate();
    expect(getGame(reloaded.getState().progress, puzzle.id).cast).toBe(true);
  });

  it('keeps the other days when a preview resets one puzzle', () => {
    const { storage } = fakeStorage();
    const store = createProgressStore(storage);
    finish(store);
    store.getState().answer(PUZZLES[1], 'linke', 'no', '2026-11-02');

    store.getState().resetGame(PUZZLES[1].id);
    const reloaded = createProgressStore(storage);
    reloaded.getState().hydrate();
    const { progress } = reloaded.getState();
    expect(getGame(progress, PUZZLES[1].id).guesses).toEqual({});
    expect(getGame(progress, puzzle.id).finishedOn).toBe(TODAY);
  });
});

describe('an older copy of the page', () => {
  const finish = (
    store: ReturnType<typeof createProgressStore>,
    answer: 'yes' | 'no',
  ) => {
    for (const party of puzzle.parties) {
      store.getState().answer(puzzle, party.partyId, answer, TODAY);
    }
  };

  // A tab left open, or a page the browser restores on "back", still holds
  // the progress from before the game was played.
  it('cannot change answers given since in a newer copy', () => {
    const { storage } = fakeStorage();
    const older = createProgressStore(storage);
    older.getState().hydrate();

    const newer = createProgressStore(storage);
    finish(newer, 'no');

    finish(older, 'yes');
    const reloaded = createProgressStore(storage);
    reloaded.getState().hydrate();
    const { guesses } = getGame(reloaded.getState().progress, puzzle.id);
    expect(Object.values(guesses).every((answer) => answer === 'no')).toBe(
      true,
    );
    // The older copy now shows the real, finished game too.
    expect(getGame(older.getState().progress, puzzle.id).finishedOn).toBe(
      TODAY,
    );
  });

  it('catches up on refresh, without anything being answered', () => {
    const { storage } = fakeStorage();
    const older = createProgressStore(storage);
    older.getState().hydrate();
    finish(createProgressStore(storage), 'no');

    older.getState().refresh();
    expect(getGame(older.getState().progress, puzzle.id).finishedOn).toBe(
      TODAY,
    );
  });

  it('keeps what this visit played when the storage could not save it', () => {
    const storage: StorageLike = {
      getItem: () => null,
      setItem: () => {
        throw new Error('QuotaExceededError');
      },
    };
    const store = createProgressStore(storage);
    store.getState().answer(puzzle, 'linke', 'no', TODAY);
    store.getState().answer(puzzle, 'spd', 'yes', TODAY);
    expect(getGame(store.getState().progress, puzzle.id).guesses).toEqual({
      linke: 'no',
      spd: 'yes',
    });
  });
});

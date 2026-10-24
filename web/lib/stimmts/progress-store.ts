import { createStore } from 'zustand/vanilla';
import {
  EMPTY_PROGRESS,
  type Progress,
  castCard,
  mergeProgress,
  parseProgress,
  recordAnswer,
  removeGame,
} from './progress';
import type { Puzzle, VoteAnswer } from './types';

export const STORAGE_KEY = 'wahlchat.stimmts.progress';

/** The part of localStorage the store needs; tests pass a fake. */
export type StorageLike = Pick<Storage, 'getItem' | 'setItem'>;

export type ProgressState = {
  progress: Progress;
  /**
   * False until the saved progress has been read. The server and the first
   * browser render both show the empty state, and the saved state is loaded
   * afterwards, so the two always agree (no hydration mismatch).
   */
  hydrated: boolean;
  hydrate: () => void;
  /**
   * Catches up with what is saved. Called when the page comes back into
   * view, since another tab, or a newer copy of this page, may have played.
   */
  refresh: () => void;
  /** Preview mode only: forget one puzzle's answers, keep the other days. */
  resetGame: (puzzleId: string) => void;
  /** Casts a finished game's Stimmkarte into the urn. */
  cast: (puzzleId: string) => void;
  answer: (
    puzzle: Puzzle,
    partyId: string,
    answer: VoteAnswer,
    today: string,
  ) => void;
};

function load(storage: StorageLike | null): Progress {
  if (!storage) {
    return EMPTY_PROGRESS;
  }
  try {
    const raw = storage.getItem(STORAGE_KEY);
    return raw ? parseProgress(JSON.parse(raw)) : EMPTY_PROGRESS;
  } catch {
    return EMPTY_PROGRESS;
  }
}

function save(storage: StorageLike | null, progress: Progress) {
  if (!storage) {
    return;
  }
  try {
    storage.setItem(STORAGE_KEY, JSON.stringify(progress));
  } catch {
    // Storage full or blocked (private mode): the game keeps working for this
    // visit, it just cannot be resumed after a reload.
  }
}

/** The browser's localStorage, or null where it is missing or blocked. */
export function browserStorage(): StorageLike | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function createProgressStore(storage: StorageLike | null) {
  return createStore<ProgressState>()((set, get) => {
    const current = () => mergeProgress(load(storage), get().progress);
    // Reading storage yields a fresh object each time; only a real change
    // should reach the components.
    const setIfChanged = (next: Progress) => {
      if (JSON.stringify(next) !== JSON.stringify(get().progress)) {
        set({ progress: next });
      }
    };

    const update = (change: (before: Progress) => Progress) => {
      // Always start from what is saved, never from this page's memory
      // alone: an older copy of the page would otherwise overwrite answers
      // given since, and answers are final.
      get().hydrate();
      const before = current();
      const after = change(before);
      setIfChanged(after);
      if (after !== before) {
        save(storage, after);
      }
    };

    return {
      progress: EMPTY_PROGRESS,
      hydrated: false,

      hydrate: () => {
        if (get().hydrated) {
          return;
        }
        set({ progress: load(storage), hydrated: true });
      },

      refresh: () => {
        if (!get().hydrated) {
          return;
        }
        setIfChanged(current());
      },

      resetGame: (puzzleId) => update((before) => removeGame(before, puzzleId)),

      cast: (puzzleId) => update((before) => castCard(before, puzzleId)),

      // Saved the moment it is tapped, so a reload cannot undo an answer.
      answer: (puzzle, partyId, answer, today) =>
        update((before) =>
          recordAnswer(before, puzzle, partyId, answer, today),
        ),
    };
  });
}

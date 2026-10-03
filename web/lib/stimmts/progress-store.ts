import { createStore } from 'zustand/vanilla';
import {
  EMPTY_PROGRESS,
  type Progress,
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
  /** Preview mode only: forget one puzzle's answers, keep the streak. */
  resetGame: (puzzleId: string) => void;
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
  return createStore<ProgressState>()((set, get) => ({
    progress: EMPTY_PROGRESS,
    hydrated: false,

    hydrate: () => {
      if (get().hydrated) {
        return;
      }
      set({ progress: load(storage), hydrated: true });
    },

    resetGame: (puzzleId) => {
      get().hydrate();
      const before = get().progress;
      const after = removeGame(before, puzzleId);
      if (after === before) {
        return;
      }
      set({ progress: after });
      save(storage, after);
    },

    answer: (puzzle, partyId, answer, today) => {
      // Never write before reading: an answer given too early would otherwise
      // replace the saved progress with a nearly empty copy.
      get().hydrate();
      const before = get().progress;
      const after = recordAnswer(before, puzzle, partyId, answer, today);
      if (after === before) {
        return;
      }
      // Saved the moment it is tapped, so a reload cannot undo an answer.
      set({ progress: after });
      save(storage, after);
    },
  }));
}

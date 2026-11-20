import { useEffect } from 'react';
import { useStore } from 'zustand';
import { createStore } from 'zustand/vanilla';
import { berlinMonth } from './berlin-time';
import { finishedGameCount } from './feedback';
import { type StorageLike, browserStorage } from './progress-store';
import {
  type StyleId,
  effectiveStyle,
  freshStyles,
  isStyleId,
  unlockedStyles,
} from './styles';
import { useProgress } from './use-progress';

export const STYLE_KEY = 'stimmts:style';
export const SEEN_KEY = 'stimmts:styles-seen';

export type StyleState = {
  chosen: StyleId;
  seen: StyleId[];
  /** False until storage is read, so server and first render agree. */
  hydrated: boolean;
  hydrate: () => void;
  choose: (id: StyleId) => void;
  markSeen: (ids: readonly StyleId[]) => void;
};

function read(storage: StorageLike | null, key: string): string | null {
  try {
    return storage?.getItem(key) ?? null;
  } catch {
    return null;
  }
}

function write(storage: StorageLike | null, key: string, value: string) {
  try {
    storage?.setItem(key, value);
  } catch {
    // Blocked or full: the choice still holds for this visit.
  }
}

function readChosen(storage: StorageLike | null): StyleId {
  const saved = read(storage, STYLE_KEY);
  return isStyleId(saved) ? saved : 'standard';
}

function readSeen(storage: StorageLike | null): StyleId[] {
  try {
    const parsed: unknown = JSON.parse(read(storage, SEEN_KEY) ?? '[]');
    return Array.isArray(parsed) ? parsed.filter(isStyleId) : [];
  } catch {
    return [];
  }
}

export function createStyleStore(storage: StorageLike | null) {
  return createStore<StyleState>()((set, get) => ({
    chosen: 'standard',
    seen: [],
    hydrated: false,

    hydrate: () => {
      if (get().hydrated) {
        return;
      }
      set({
        chosen: readChosen(storage),
        seen: readSeen(storage),
        hydrated: true,
      });
    },

    choose: (id) => {
      set({ chosen: id });
      write(storage, STYLE_KEY, id);
    },

    markSeen: (ids) => {
      const seen = [...new Set([...get().seen, ...ids])];
      if (seen.length === get().seen.length) {
        return;
      }
      set({ seen });
      write(storage, SEEN_KEY, JSON.stringify(seen));
    },
  }));
}

// Filled only in the browser after mount, like the progress store, so the
// instance the server creates never carries one player's choice to another.
export const styleStore = createStyleStore(browserStorage());

/**
 * The style to draw now, the styles not yet looked at, and the days played.
 * Before hydration this is the standard look with nothing new, which is what
 * the server renders.
 */
export function useStimmtsStyle(): {
  style: StyleId;
  fresh: StyleId[];
  daysPlayed: number;
} {
  const chosen = useStore(styleStore, (state) => state.chosen);
  const seen = useStore(styleStore, (state) => state.seen);
  const styleHydrated = useStore(styleStore, (state) => state.hydrated);
  const progress = useProgress((state) => state.progress);
  const progressHydrated = useProgress((state) => state.hydrated);
  const hydrateProgress = useProgress((state) => state.hydrate);

  useEffect(() => {
    styleStore.getState().hydrate();
    hydrateProgress();
  }, [hydrateProgress]);

  const daysPlayed = progressHydrated ? finishedGameCount(progress) : 0;
  if (!styleHydrated || !progressHydrated) {
    return { style: 'standard', fresh: [], daysPlayed };
  }
  const month = berlinMonth(new Date());
  return {
    style: effectiveStyle(chosen, daysPlayed, month),
    fresh: freshStyles(unlockedStyles(daysPlayed, month), seen),
    daysPlayed,
  };
}

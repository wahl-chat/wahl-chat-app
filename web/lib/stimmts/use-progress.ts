import { useStore } from 'zustand';
import {
  type ProgressState,
  browserStorage,
  createProgressStore,
} from './progress-store';

// One store for the whole page. It is only ever filled in the browser, after
// mount (see `hydrate`), so the instance the server creates stays empty and
// can never leak one player's progress into another's response.
const progressStore = createProgressStore(browserStorage());

export function useProgress<T>(selector: (state: ProgressState) => T): T {
  return useStore(progressStore, selector);
}

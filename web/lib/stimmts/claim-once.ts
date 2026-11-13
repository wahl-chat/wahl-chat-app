import type { StorageLike } from './progress-store';

/**
 * True the first time a key is claimed in this browser and false ever after,
 * across reloads and tabs. Without storage it is always true: an event may
 * then be counted twice, but it is never lost.
 */
export function claimOnce(storage: StorageLike | null, key: string): boolean {
  if (!storage) {
    return true;
  }
  try {
    if (storage.getItem(key) !== null) {
      return false;
    }
    storage.setItem(key, '1');
  } catch {
    // Storage blocked: count it, as without storage.
  }
  return true;
}

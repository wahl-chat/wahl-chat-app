const OPENED_KEY = 'wahlchat.meineWocheOpened';

/** Whether this browser has opened "Meine Woche" before. A store that cannot
 * be read counts as opened, so the "new" dot never nags without a way to
 * remember that it was seen. */
export function weeklySignupOpened(
  storage: Pick<Storage, 'getItem'> = window.localStorage,
): boolean {
  try {
    return storage.getItem(OPENED_KEY) === 'true';
  } catch {
    return true;
  }
}

export function markWeeklySignupOpened(
  storage: Pick<Storage, 'setItem'> = window.localStorage,
): void {
  try {
    storage.setItem(OPENED_KEY, 'true');
  } catch {
    // The dot then shows again next visit; nothing else depends on it.
  }
}

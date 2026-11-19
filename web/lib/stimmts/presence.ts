import { STORAGE_KEY } from './progress-store';

export type Presence = 'today' | 'before' | null;

/** sessionStorage flag the game sets on finishing, so the feed can animate once. */
export const JUST_PLAYED_KEY = 'stimmts:just-played';

/**
 * Whether the saved progress holds a game finished today, only older ones, or
 * none. Serialised with toString() into an inline script that runs before
 * first paint, so it must not import or close over anything. It reads the raw
 * JSON itself and trusts nothing: junk, other versions and odd shapes are null.
 */
export function presenceOf(raw: string | null, today: string): Presence {
  try {
    const saved = raw ? JSON.parse(raw) : null;
    if (
      !saved ||
      typeof saved !== 'object' ||
      saved.version !== 1 ||
      !saved.games ||
      typeof saved.games !== 'object'
    ) {
      return null;
    }
    let before = false;
    for (const id of Object.keys(saved.games)) {
      const game = saved.games[id];
      const finishedOn = game?.finishedOn;
      if (typeof finishedOn !== 'string') {
        continue;
      }
      if (finishedOn === today) {
        return 'today';
      }
      before = true;
    }
    return before ? 'before' : null;
  } catch {
    return null;
  }
}

type SessionLike = Pick<Storage, 'setItem' | 'removeItem'>;
type RootLike = { dataset: DOMStringMap | Record<string, string | undefined> };

/** sessionStorage, or null where reading it throws (blocked site data). */
export function browserSession(): SessionLike | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

/**
 * Called by the page that finishes today's game. The flag lets a reload of
 * the feed fly the card in; the marks on <html> do it for the feed reached
 * by a client-side navigation, where the presence script does not run again.
 */
export function markJustPlayed(
  today: string,
  session: SessionLike | null,
  root: RootLike,
): void {
  try {
    session?.setItem(JUST_PLAYED_KEY, today);
  } catch {
    // Blocked storage: only a reload loses the flight.
  }
  root.dataset.stimmts = 'today';
  root.dataset.stimmtsFly = '';
}

/** The flight plays once: after it, and on a page restored from history. */
export function clearJustPlayed(
  session: SessionLike | null,
  root: RootLike,
): void {
  try {
    session?.removeItem(JUST_PLAYED_KEY);
  } catch {
    // Nothing to clear when storage is blocked.
  }
  delete root.dataset.stimmtsFly;
}

// The feed page is cached and shared, so the device-specific state is set on
// <html> before first paint instead of rendered; CSS then shows the right
// variant without a flash. Storage can throw (blocked), hence the try.
const BERLIN_TODAY =
  "new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Berlin',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())";

export const PRESENCE_SCRIPT = `try{var t=${BERLIN_TODAY};var p=(${presenceOf.toString()})(localStorage.getItem(${JSON.stringify(
  STORAGE_KEY,
)}),t);var d=document.documentElement;if(p){d.dataset.stimmts=p}if(sessionStorage.getItem(${JSON.stringify(
  JUST_PLAYED_KEY,
)})===t){d.dataset.stimmtsFly=''}}catch(e){}`;

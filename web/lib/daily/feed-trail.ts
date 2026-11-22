/** How many feed items were opened from within another one up to this
 * history entry. Stored in the entry's state, so Back and Forward agree. */
const DEPTH_KEY = 'feedDepth';

export function trailDepth(state: unknown): number {
  if (state && typeof state === 'object' && DEPTH_KEY in state) {
    const depth = (state as Record<string, unknown>)[DEPTH_KEY];
    return typeof depth === 'number' && depth > 0 ? Math.floor(depth) : 0;
  }
  return 0;
}

/** The entry state for an item opened one level deeper, keeping what else
 * the entry carries. */
export function deeperState(state: unknown): Record<string, unknown> {
  const base =
    state && typeof state === 'object'
      ? (state as Record<string, unknown>)
      : {};
  return { ...base, [DEPTH_KEY]: trailDepth(state) + 1 };
}

/** The item key a feed link points at. */
export function feedItemKeyOf(href: string): string | null {
  return new URL(href, 'https://wahl.chat').searchParams.get('item');
}

type Click = {
  button: number;
  metaKey: boolean;
  ctrlKey: boolean;
  shiftKey: boolean;
  altKey: boolean;
};

/** A plain left click; any modifier keeps the browser's own handling
 * (new tab, new window, download). */
export function isPlainClick(event: Click): boolean {
  return (
    event.button === 0 &&
    !event.metaKey &&
    !event.ctrlKey &&
    !event.shiftKey &&
    !event.altKey
  );
}

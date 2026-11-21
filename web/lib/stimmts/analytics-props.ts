import { addDays } from './berlin-time';
import type { ChatChipId } from './chat-chips';
import { finishedGameCount } from './feedback';
import type { Progress } from './progress';

// Pure builders for the properties the game's analytics events carry. They
// are worked out on the device because Vercel Analytics has no stable visitor
// id: whether a player is new or returning, and where they came from, can
// only be told from what this browser remembers. Every value is a string,
// number, boolean or null, which is all `track` accepts.

export type RetentionProps = {
  games_before: number;
  played_yesterday: boolean;
};

/**
 * Whether this is a first game or a returning player's, without any id: how
 * many games the device had finished before this puzzle, and whether one of
 * them was finished on the previous Berlin day. The current puzzle is left
 * out, so the same numbers come out when the game starts and when it ends.
 */
export function retentionProps(
  progress: Progress,
  puzzleId: string,
  today: string,
): RetentionProps {
  const { [puzzleId]: _current, ...others } = progress.games;
  const before: Progress = { ...progress, games: others };
  const yesterday = addDays(today, -1);
  return {
    games_before: finishedGameCount(before),
    played_yesterday: Object.values(others).some(
      (game) => game.finishedOn === yesterday,
    ),
  };
}

export type EntrySource =
  | 'feed_card'
  | 'header_icon'
  | 'shared_link'
  | 'direct';

type MarkedSource = 'feed_card' | 'header_icon';

type MarkerStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

export const ENTRY_MARKER_KEY = 'stimmts:entry';

/**
 * A click that leaves the page cannot hand its source to the game page in
 * memory, so it leaves a marker for the page to find. Ten minutes covers a
 * slow load; an older marker is a tab that was left open and came back to
 * later, which is not the click that started this game.
 */
export const ENTRY_MARKER_MAX_AGE_MS = 10 * 60 * 1000;

const MARKED_SOURCES: readonly string[] = ['feed_card', 'header_icon'];

/** Per tab (sessionStorage), so another tab's click never claims this start. */
export function markEntry(
  source: MarkedSource,
  storage: MarkerStorage | null,
  now: number,
): void {
  try {
    storage?.setItem(ENTRY_MARKER_KEY, `${source}:${now}`);
  } catch {
    // Without storage the start counts as direct.
  }
}

function readMarker(storage: MarkerStorage | null, now: number) {
  try {
    const raw = storage?.getItem(ENTRY_MARKER_KEY);
    storage?.removeItem(ENTRY_MARKER_KEY);
    if (!raw) {
      return null;
    }
    const [source, time] = raw.split(':');
    const age = now - Number(time);
    if (
      !MARKED_SOURCES.includes(source) ||
      !Number.isFinite(age) ||
      age < 0 ||
      age > ENTRY_MARKER_MAX_AGE_MS
    ) {
      return null;
    }
    return source as MarkedSource;
  } catch {
    return null;
  }
}

/**
 * How the player got to the game. A challenge link wins over a marker: the
 * friend's link is what brought them, even if they had clicked the feed card
 * earlier. The marker is cleared either way, so it can only count once.
 */
export function resolveEntry(input: {
  sharedLink: boolean;
  storage: MarkerStorage | null;
  now: number;
}): EntrySource {
  const marked = readMarker(input.storage, input.now);
  if (input.sharedLink) {
    return 'shared_link';
  }
  return marked ?? 'direct';
}

export type ChatAskedProps = {
  kind: 'chip' | 'typed';
  chip: ChatChipId | null;
  day: number;
};

/**
 * Which kind of question was asked. The text is never part of it: a typed
 * question is the player's own words, and a chip's text names a party.
 */
export function chatAskedProps(
  asked: { chip: ChatChipId | null },
  day: number,
): ChatAskedProps {
  return {
    kind: asked.chip ? 'chip' : 'typed',
    chip: asked.chip,
    day,
  };
}

import { track } from '@vercel/analytics/react';
import {
  type ChatAskedProps,
  type EntrySource,
  chatAskedProps,
  markEntry,
  resolveEntry,
  retentionProps,
} from './analytics-props';
import type { ChatChipId } from './chat-chips';
import { claimOnce } from './claim-once';
import type { Progress } from './progress';
import { browserStorage } from './progress-store';

// Counts and categories only: never the tips, never typed text, never an id.
// A player's tips are predictions, but a log of them per party could still be
// read as views. The retention and entry props exist so the team can tell
// whether the game brings new people to the platform (entry, games_before)
// and whether they come back the next day (played_yesterday). Vercel has no
// stable visitor id, so those facts are worked out on the device. The events
// and their props are listed in docs/stimmts/DESIGN.md.

function browserSessionStorage(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.sessionStorage;
  } catch {
    return null;
  }
}

/** Where the game page was opened from; the next start reads it. */
export function rememberEntry(source: 'feed_card' | 'header_icon') {
  markEntry(source, browserSessionStorage(), Date.now());
}

/** Once per puzzle and browser: not again after a reload or in another tab. */
export function trackPuzzleStarted(
  day: number,
  puzzleId: string,
  progress: Progress,
  today: string,
  sharedLink: boolean,
) {
  // Read even when the start is not counted, so a repeat start cannot leave a
  // stale marker behind for a later puzzle to claim.
  const entry: EntrySource = resolveEntry({
    sharedLink,
    storage: browserSessionStorage(),
    now: Date.now(),
  });
  if (claimOnce(browserStorage(), `stimmts:started:${puzzleId}`)) {
    track('stimmts_puzzle_started', {
      day,
      entry,
      ...retentionProps(progress, puzzleId, today),
    });
  }
}

export function trackPuzzleCompleted(
  day: number,
  score: number,
  puzzleId: string,
  progress: Progress,
  today: string,
) {
  track('stimmts_puzzle_completed', {
    day,
    score,
    ...retentionProps(progress, puzzleId, today),
  });
}

/** One per question asked in the chat card, by chip id or as typed. */
export function trackChatAsked(chip: ChatChipId | null, day: number) {
  const props: ChatAskedProps = chatAskedProps({ chip }, day);
  track('stimmts_chat_asked', props);
}

export type MoreGamesAnswer = 'yes' | 'no' | 'dismissed';

/**
 * Whether players want more small games, asked once after the first finished
 * puzzle. A close without an answer is 'dismissed', so skips count too. The
 * rows without a `placement` came from the result screen.
 */
export function trackMoreGames(
  answer: MoreGamesAnswer,
  games: number,
  placement: 'feed',
) {
  track('stimmts_more_games', { answer, games, placement });
}

export type ShareMethod = 'share' | 'copy';

/** From a day's result, or from the closing screen after the last day. */
export function trackResultShared(
  screen: 'result' | 'closing',
  method: ShareMethod,
  day?: number,
) {
  track('stimmts_result_shared', { screen, method, day: day ?? null });
}

import { PUZZLE_COUNT } from './content';
import { MAX_SCORE, parseShareParams } from './share-image';

/**
 * Whether the page was opened from a shared result, whatever day it is from.
 * Unlike the challenge this has no day check: a friend who opens a link
 * shared yesterday was still brought by it, even though no banner shows.
 */
export function isSharedLink(search: string, today: string): boolean {
  return (
    parseShareParams(new URLSearchParams(search), PUZZLE_COUNT, today)
      ?.result != null
  );
}

/**
 * The line that challenges a friend who opens a shared result, or null when
 * there is nothing to challenge. Only a result from today's puzzle counts:
 * another day's score is a different quiz, so beating it means nothing. The
 * link is read with the same checks as the share image, because anyone can
 * type these parameters.
 */
export function shareChallenge({
  search,
  today,
  playedToday,
}: {
  search: string;
  today: string;
  playedToday: boolean;
}): { score: number; text: string } | null {
  if (playedToday) {
    return null;
  }
  const shared = parseShareParams(
    new URLSearchParams(search),
    PUZZLE_COUNT,
    today,
  )?.result;
  if (!shared || shared.playDate !== today) {
    return null;
  }
  const { score } = shared;
  // A perfect score cannot be beaten, only matched.
  return {
    score,
    text:
      score === MAX_SCORE
        ? `Schaffst du auch ${score}/${MAX_SCORE}?`
        : `Schaffst du mehr als ${score}/${MAX_SCORE}?`,
  };
}

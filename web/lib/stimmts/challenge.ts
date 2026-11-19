import { PUZZLE_COUNT } from './content';
import { MAX_SCORE, parseShareParams } from './share-image';

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
}): string | null {
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
  // A perfect score cannot be beaten, only matched.
  return shared.score === MAX_SCORE
    ? `Schaffst du auch ${shared.score}/${MAX_SCORE}?`
    : `Schaffst du mehr als ${shared.score}/${MAX_SCORE}?`;
}

import type { PuzzleScore } from './score';

type ShareInput = {
  puzzleNumber: number;
  topic: string;
  score: PuzzleScore;
  url: string;
};

/**
 * The text a player shares. The grid shows only whether each seat was right,
 * in seating order, so it spoils nothing and reveals nothing about the
 * player's own views (they were predictions, not opinions).
 */
export function buildShareText({
  puzzleNumber,
  topic,
  score,
  url,
}: ShareInput): string {
  const grid = score.parties.map((party) => (party.correct ? '🟩' : '🟥'));
  return [
    `Stimmt's? #${puzzleNumber} · ${topic} · ${score.correct}/${score.total}`,
    grid.join(''),
    url,
  ].join('\n');
}

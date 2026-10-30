import type { PeriodSummary } from './period';
import type { PuzzleScore } from './score';

type ShareInput = {
  puzzleNumber: number;
  score: PuzzleScore;
  url: string;
};

/**
 * The text a player shares: the score and an invitation, nothing else. It
 * deliberately says nothing about which parties were right or wrong, so it
 * gives the friend who opens it no hint about today's answers (and reveals
 * nothing about the player's own views: they were predictions, not opinions).
 */
export function buildShareText({
  puzzleNumber,
  score,
  url,
}: ShareInput): string {
  const squares =
    '🟩'.repeat(score.correct) + '⬜'.repeat(score.total - score.correct);
  return [
    `Stimmt's? #${puzzleNumber} · ${score.correct}/${score.total} ${squares}`,
    '',
    'Schlag meinen Score im neuen Spiel von wahl.chat: Wie haben die Parteien im Bundestag abgestimmt?',
    url,
  ].join('\n');
}

type ClosingShareInput = {
  summary: PeriodSummary;
  /** How many days the game ran. */
  days: number;
  url: string;
};

/** The text shared once the game is over: the whole run, in numbers only. */
export function buildClosingShareText({
  summary,
  days,
  url,
}: ClosingShareInput): string {
  return [
    `Stimmt's? · ${summary.played} von ${days} Tagen gespielt · ${summary.correct}/${summary.possible} richtig`,
    '',
    'Das Rätsel von wahl.chat: Wie haben die Parteien im Bundestag abgestimmt?',
    url,
  ].join('\n');
}

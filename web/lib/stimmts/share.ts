import type { PeriodSummary } from './period';
import type { PuzzleScore } from './score';

type Score = Pick<PuzzleScore, 'correct' | 'total'>;

type ShareInput = {
  puzzleNumber: number;
  score: Score;
  /** The vote's title, as the start screen shows it. */
  title: string;
  url: string;
};

/** The challenge to the friend: beat the score, or match a perfect one. */
export function shareInvitation({ correct, total }: Score): string {
  return correct === total ? 'Schaffst du das auch?' : 'Schaffst du mehr?';
}

/**
 * The text a player shares: the vote, the score and a challenge. The title
 * is public on the start screen, so naming it gives nothing away; the text
 * deliberately says nothing about which parties were right or wrong, so it
 * gives the friend who opens it no hint about the answers (and reveals
 * nothing about the player's own views: they were predictions, not opinions).
 */
export function buildShareText({
  puzzleNumber,
  score,
  title,
  url,
}: ShareInput): string {
  const squares =
    '🟩'.repeat(score.correct) + '⬜'.repeat(score.total - score.correct);
  return [
    `Stimmt's? #${puzzleNumber} · ${score.correct}/${score.total} ${squares}`,
    '',
    `${title}: Wie haben die Fraktionen abgestimmt? Ich hatte ${score.correct} von ${score.total}. ${shareInvitation(score)}`,
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
    'Das Quiz von wahl.chat: Wie haben die Parteien im Bundestag abgestimmt?',
    url,
  ].join('\n');
}

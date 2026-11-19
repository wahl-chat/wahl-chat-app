import { chatQuestion } from './chat-question';
import { ANSWER_LABELS } from './labels';
import type { Guesses, Puzzle } from './types';

/**
 * Off until the general chat exists: the card on the result screen stays
 * hidden, its logic stays in place. Its answers are a local placeholder until
 * then, so switching it on before that would show players a fake answer.
 */
export const STIMMTS_CHAT_ENABLED = false;

export type ChatChip = {
  /** What the chip shows, short enough to sit three to a row on a phone. */
  label: string;
  /** What the chat is asked, in full. */
  question: string;
};

/**
 * How a chip names each Fraktion: as short as the name gets. Not partyLabel:
 * "Bündnis 90/Die Grünen" and "CDU/CSU" would push "Warum Nein, …?" past
 * what fits on a chip.
 */
const SHORT_NAMES: Record<string, string> = {
  linke: 'Linke',
  spd: 'SPD',
  gruene: 'Grüne',
  cdu: 'Union',
  afd: 'AfD',
};

/** The chat context whose parties sit in the Bundestag. */
const CHAT_CONTEXT = 'bundestagswahl-2025';

/**
 * Three chips: first the party the player got wrong (or, with nothing wrong,
 * the vote's biggest surprise), then where the bill stands. The bill's status
 * is not part of a puzzle, so those two leave it to the chat to look up.
 */
export function chatChips(puzzle: Puzzle, guesses: Guesses): ChatChip[] {
  return [
    firstChip(puzzle, guesses),
    {
      label: 'Schon in Kraft?',
      question: `Ist „${puzzle.title}“ schon in Kraft?`,
    },
    {
      label: 'Wie geht’s weiter?',
      question: `Wie geht es mit „${puzzle.title}“ nach der Abstimmung weiter?`,
    },
  ];
}

function firstChip(puzzle: Puzzle, guesses: Guesses): ChatChip {
  const asked = chatQuestion(puzzle, guesses);
  const [partyId] = asked.partyIds;
  const actual = puzzle.parties.find(
    (party) => party.partyId === partyId,
  )?.answer;
  if (asked.kind === 'wrong-guess' && actual && SHORT_NAMES[partyId]) {
    return {
      label: `Warum ${ANSWER_LABELS[actual]}, ${SHORT_NAMES[partyId]}?`,
      question: asked.text,
    };
  }
  return {
    label: 'Überraschendste Stimme?',
    question: `Welche Stimme war bei der Abstimmung „${puzzle.title}“ am überraschendsten, und warum?`,
  };
}

function formatDate(isoDay: string): string {
  const [year, month, day] = isoDay.split('-');
  return `${day}.${month}.${year}`;
}

/**
 * The chat has no channel for structured context, so the vote travels in the
 * question itself, as it does from the parliament feed.
 */
export function stimmtsChatHref(
  puzzle: Puzzle,
  question: string,
  partyIds: string[],
): string {
  const params = new URLSearchParams({
    q: `Zur Abstimmung „${puzzle.title}“ im Bundestag am ${formatDate(
      puzzle.voteDate,
    )}: ${question.trim()}`,
  });
  for (const id of partyIds) {
    params.append('party_id', id);
  }
  return `/${CHAT_CONTEXT}/session?${params}`;
}

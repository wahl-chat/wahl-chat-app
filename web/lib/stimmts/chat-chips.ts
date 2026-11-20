import { chatQuestion } from './chat-question';
import { ANSWER_LABELS } from './labels';
import type { Guesses, Puzzle } from './types';

/**
 * Off until the general chat is merged into `develop`: the card on the result
 * screen opens that chat, so switching it on earlier would send players to a
 * page that cannot answer.
 */
export const STIMMTS_CHAT_ENABLED = false;

export type ChatChipId = 'why_party' | 'surprise' | 'in_force' | 'next';

export type ChatChip = {
  /**
   * Stable across wording changes: what analytics records instead of the
   * chip's text, which names a party.
   */
  id: ChatChipId;
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

/**
 * Three chips: first the party the player got wrong (or, with nothing wrong,
 * the vote's biggest surprise), then where the bill stands. The bill's status
 * is not part of a puzzle, so those two leave it to the chat to look up.
 */
export function chatChips(puzzle: Puzzle, guesses: Guesses): ChatChip[] {
  return [
    firstChip(puzzle, guesses),
    {
      id: 'in_force',
      label: 'Schon in Kraft?',
      question: `Ist „${puzzle.title}“ schon in Kraft?`,
    },
    {
      id: 'next',
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
      id: 'why_party',
      label: `Warum ${ANSWER_LABELS[actual]}, ${SHORT_NAMES[partyId]}?`,
      question: asked.text,
    };
  }
  return {
    id: 'surprise',
    label: 'Überraschendste Stimme?',
    question: `Welche Stimme war bei der Abstimmung „${puzzle.title}“ am überraschendsten, und warum?`,
  };
}

/**
 * The general chat anchored on the day's vote. The anchor card carries the
 * vote's identity, so the question travels bare: no party filter (the chat
 * finds the parties from the vote) and no preset (those belong to feed items,
 * and these chips are our own questions).
 */
export function stimmtsChatHref(puzzle: Puzzle, question: string): string {
  const params = new URLSearchParams({
    q: question.trim(),
    poll_id: String(puzzle.pollId),
  });
  return `/chat?${params}`;
}

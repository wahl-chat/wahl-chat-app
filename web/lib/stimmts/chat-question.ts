import { SEATING_ORDER } from './parties';
import { scorePuzzle } from './score';
import type { Guesses, Puzzle, VoteAnswer } from './types';

export type ChatQuestionKind =
  | 'wrong-guess'
  | 'unusual-allies'
  | 'coalition-split'
  | 'general';

export type ChatQuestion = {
  kind: ChatQuestionKind;
  text: string;
  /** The Fraktionen the question names, so the chat can scope its search. */
  partyIds: string[];
};

/**
 * How each Fraktion reads inside a German sentence. These are not the display
 * names from labels.ts: a sentence needs the article, and the Grünen are a
 * plural, so the verb changes with them ("haben", not "hat").
 */
const SUBJECTS: Record<string, { name: string; plural: boolean }> = {
  linke: { name: 'Die Linke', plural: false },
  spd: { name: 'die SPD', plural: false },
  gruene: { name: 'die Grünen', plural: true },
  cdu: { name: 'die Union (CDU/CSU)', plural: false },
  afd: { name: 'die AfD', plural: false },
};

/**
 * The questions only state what happened in the vote. The player's own tips
 * decide which question is asked, but never appear in it, so they stay on the
 * device.
 */
export function chatQuestion(puzzle: Puzzle, guesses: Guesses): ChatQuestion {
  return (
    wrongGuessQuestion(puzzle, guesses) ??
    unusualAlliesQuestion(puzzle) ??
    coalitionSplitQuestion(puzzle) ?? {
      kind: 'general',
      text: `Worum ging es bei der Abstimmung „${puzzle.title}“?`,
      partyIds: [],
    }
  );
}

function answerOf(puzzle: Puzzle, partyId: string): VoteAnswer | undefined {
  return puzzle.parties.find((party) => party.partyId === partyId)?.answer;
}

/** The party the player got wrong that stood most alone in its answer. */
function wrongGuessQuestion(
  puzzle: Puzzle,
  guesses: Guesses,
): ChatQuestion | null {
  const wrong = scorePuzzle(puzzle, guesses).parties.filter(
    (party) =>
      !party.correct && party.guess !== null && party.partyId in SUBJECTS,
  );

  const sharedWith = (partyId: string, answer: VoteAnswer) =>
    puzzle.parties.filter(
      (party) => party.partyId !== partyId && party.answer === answer,
    ).length;
  const seat = (partyId: string) => SEATING_ORDER.indexOf(partyId);
  const [mostAlone] = wrong.sort(
    (a, b) =>
      sharedWith(a.partyId, a.actual) - sharedWith(b.partyId, b.actual) ||
      seat(a.partyId) - seat(b.partyId),
  );
  if (!mostAlone) return null;

  const subject = SUBJECTS[mostAlone.partyId];
  const verb = subject.plural ? 'haben' : 'hat';
  const text =
    mostAlone.actual === 'abstain'
      ? `Warum ${verb} sich ${subject.name} enthalten?`
      : `Warum ${verb} ${subject.name} mit ${
          mostAlone.actual === 'yes' ? 'Ja' : 'Nein'
        } gestimmt?`;
  return { kind: 'wrong-guess', text, partyIds: [mostAlone.partyId] };
}

function unusualAlliesQuestion(puzzle: Puzzle): ChatQuestion | null {
  const linke = answerOf(puzzle, 'linke');
  if (linke === undefined || linke !== answerOf(puzzle, 'afd')) return null;
  // When everyone voted alike, the two agreeing is no surprise.
  const allAlike = SEATING_ORDER.every(
    (partyId) => answerOf(puzzle, partyId) === linke,
  );
  if (allAlike) return null;
  return {
    kind: 'unusual-allies',
    text: 'Warum haben Die Linke und die AfD hier gleich abgestimmt?',
    partyIds: ['linke', 'afd'],
  };
}

function coalitionSplitQuestion(puzzle: Puzzle): ChatQuestion | null {
  const cdu = answerOf(puzzle, 'cdu');
  const spd = answerOf(puzzle, 'spd');
  if (cdu === undefined || spd === undefined || cdu === spd) return null;
  return {
    kind: 'coalition-split',
    text: 'Warum haben Union und SPD hier unterschiedlich abgestimmt?',
    partyIds: ['cdu', 'spd'],
  };
}

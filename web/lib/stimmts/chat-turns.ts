import type { ChatAnswerEvent, ChatAnswerSource } from './chat-answer';
import type { ChatChip } from './chat-chips';

export type ChatTurn = {
  /** Keys the turn: the same question can be asked twice. */
  id: number;
  question: string;
  answer: string;
  sources: ChatAnswerSource[];
  status: 'streaming' | 'done' | 'error';
  /** Whether an older turn is unfolded; the latest is always shown open. */
  open: boolean;
};

/**
 * Adds the question as a streaming turn. Only the latest answer stays open,
 * so the card does not push the result off the screen.
 */
export function appendTurn(
  turns: ChatTurn[],
  id: number,
  question: string,
): ChatTurn[] {
  return [
    ...turns.map((turn) => (turn.open ? { ...turn, open: false } : turn)),
    {
      id,
      question: question.trim(),
      answer: '',
      sources: [],
      status: 'streaming',
      open: true,
    },
  ];
}

export function applyEvent(turn: ChatTurn, event: ChatAnswerEvent): ChatTurn {
  if (turn.status !== 'streaming') return turn;
  switch (event.kind) {
    case 'text':
      return { ...turn, answer: turn.answer + event.delta };
    case 'sources':
      // A later list covers sources a tool found after the text began.
      return { ...turn, sources: event.sources };
    case 'done':
      return {
        ...turn,
        status: 'done',
        answer: event.text ? event.text : turn.answer,
      };
    case 'error':
      return { ...turn, status: 'error' };
  }
}

/** A stream that ended without saying how is a failed answer. */
export function finishTurn(turn: ChatTurn): ChatTurn {
  return turn.status === 'streaming' ? { ...turn, status: 'error' } : turn;
}

export function toggleTurn(turns: ChatTurn[], id: number): ChatTurn[] {
  return turns.map((turn) =>
    turn.id === id ? { ...turn, open: !turn.open } : turn,
  );
}

export function isStreaming(turns: ChatTurn[]): boolean {
  return turns.some((turn) => turn.status === 'streaming');
}

/** A chip asks once: after that its answer is in the card already. */
export function remainingChips(
  chips: ChatChip[],
  turns: ChatTurn[],
): ChatChip[] {
  const asked = new Set(turns.map((turn) => turn.question));
  return chips.filter((chip) => !asked.has(chip.question));
}

/** What the chat is told was said before: answered turns only. */
export function turnHistory(
  turns: ChatTurn[],
): { question: string; answer: string }[] {
  return turns
    .filter((turn) => turn.status === 'done' && turn.answer)
    .map(({ question, answer }) => ({ question, answer }));
}

const CITATION = /\s?\[\d+(?:\s*,\s*\d+)*\]/g;
/** A marker cut off at the end of what has streamed so far. */
const PARTIAL_CITATION = /\s?\[(?:\d+(?:\s*,\s*\d*)*)?$/;

/**
 * The answer without its "[n]" citation markers: the card lists the sources
 * as pills under the answer instead of linking each sentence.
 */
export function answerText(answer: string): string {
  return answer.replace(CITATION, '').replace(PARTIAL_CITATION, '');
}

export function sourceNames(sources: ChatAnswerSource[]): string {
  return [...new Set(sources.map((source) => source.label))].join(' · ');
}

export type SourcePill = {
  /** What the pill shows. */
  text: string;
  /** What a screen reader hears. */
  label: string;
  url: string;
};

/**
 * One source is named on its pill. Several are numbered, so the row stays
 * short, and named together on a line below.
 */
export function sourcePills(sources: ChatAnswerSource[]): {
  pills: SourcePill[];
  names: string | null;
} {
  if (sources.length === 1) {
    const [{ label, url }] = sources;
    return { pills: [{ text: label, label, url }], names: null };
  }
  return {
    pills: sources.map(({ label, url }, i) => ({
      text: String(i + 1),
      label: `Quelle ${i + 1}: ${label}`,
      url,
    })),
    names: sources.length > 0 ? sourceNames(sources) : null,
  };
}

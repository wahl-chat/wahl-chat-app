import type { AnswerSource } from '@/lib/firebase/firebase.types';
import type { Source } from '@/lib/stores/chat-store.types';
import { type DetailItem, suggestedQuestions } from './items';

/** A suggested question with its precomputed answer, ready for the chat's
 * renderer: `[n]` counts from 0 into `sources`. */
export type InlineAnswer = {
  question: string;
  text: string;
  sources: Source[];
};

export type ItemQuestions = {
  /** Questions with an answer: accordion rows. */
  answers: InlineAnswer[];
  /** Questions without one: chips that hand over to the chat. */
  chips: string[];
};

const CITATION = /\[(\d+(?:\s*,\s*\d+)*)]/g;

/**
 * The feed's answers cite from 1, the chat's renderer counts from 0.
 * Numbers without a source are dropped, and a citation left empty with them.
 */
export function toChatCitations(text: string, sourceCount: number): string {
  return text.replace(CITATION, (_, numbers: string) => {
    const kept = numbers
      .split(',')
      .map((n) => Number.parseInt(n.trim(), 10))
      .filter((n) => n >= 1 && n <= sourceCount)
      .map((n) => String(n - 1));
    return kept.length > 0 ? `[${kept.join(', ')}]` : '';
  });
}

export function toChatSource(source: AnswerSource): Source {
  return {
    source: source.source,
    source_document: source.source,
    url: source.url ?? source.video_url ?? source.pdf_url ?? '',
    page: source.page ?? 1,
    document_publish_date: source.document_publish_date ?? '',
    party_id: source.party_id ?? undefined,
    source_type: source.source_type ?? undefined,
    video_url: source.video_url ?? undefined,
    pdf_url: source.pdf_url ?? undefined,
    snippet: source.snippet ?? undefined,
  };
}

/** Pairs each suggested question with its answer by index; one without an
 * answer (null, empty or past the list) stays a chip. */
export function itemQuestions(item: DetailItem): ItemQuestions {
  const answers =
    (item.kind === 'section'
      ? item.section.suggested_answers
      : item.vote.suggested_answers) ?? [];
  const result: ItemQuestions = { answers: [], chips: [] };
  suggestedQuestions(item).forEach((question, i) => {
    const answer = answers[i];
    if (answer?.text.trim()) {
      result.answers.push({
        question,
        text: toChatCitations(answer.text, answer.sources.length),
        sources: answer.sources.map(toChatSource),
      });
    } else {
      result.chips.push(question);
    }
  });
  return result;
}

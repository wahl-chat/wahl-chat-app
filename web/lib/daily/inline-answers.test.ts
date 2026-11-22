import { describe, expect, it } from 'bun:test';
import type { DailyDigest, DigestVote } from '@/lib/firebase/firebase.types';
import { itemQuestions, toChatCitations } from './inline-answers';
import { voteItems } from './items';

const SOURCE = {
  source: 'Plenarprotokoll 21/90',
  url: 'https://dserver.bundestag.de/btp/21/21090.pdf',
  page: 12,
  source_type: 'parliamentary_speech' as const,
  party_id: 'spd',
  snippet: 'Wir stabilisieren die Beiträge.',
  video_url: null,
  pdf_url: 'https://dserver.bundestag.de/btp/21/21090.pdf',
  document_publish_date: '2026-07-10',
};

function voteWith(vote: Partial<DigestVote>) {
  const digest: DailyDigest = {
    id: 'bundestag_2026-07-10',
    parliament: 'bundestag',
    parliament_name: 'Bundestag',
    region: 'DE',
    date: '2026-07-10',
    votes: [
      {
        poll_id: 7,
        title: 'Gesetzentwurf',
        short_title: 'Stabile Kassenbeiträge',
        summary: null,
        topics: [],
        outcome: 'angenommen',
        citation_url: null,
        parties: [],
        ...vote,
      },
    ],
    session: null,
  };
  return voteItems(digest)[0];
}

describe('itemQuestions', () => {
  it('turns answered questions into rows and keeps the rest as chips', () => {
    const { answers, chips } = itemQuestions(
      voteWith({
        suggested_questions: ['Wer war dagegen?', 'Was kostet das?'],
        suggested_answers: [
          { text: 'Die AfD stimmte dagegen [1].', sources: [SOURCE] },
          { text: '', sources: [] },
        ],
      }),
    );
    expect(answers).toEqual([
      {
        question: 'Wer war dagegen?',
        text: 'Die AfD stimmte dagegen [0].',
        sources: [
          {
            source: 'Plenarprotokoll 21/90',
            source_document: 'Plenarprotokoll 21/90',
            url: SOURCE.url,
            page: 12,
            document_publish_date: '2026-07-10',
            party_id: 'spd',
            source_type: 'parliamentary_speech',
            video_url: undefined,
            pdf_url: SOURCE.pdf_url,
            snippet: 'Wir stabilisieren die Beiträge.',
          },
        ],
      },
    ]);
    expect(chips).toEqual(['Was kostet das?']);
  });

  it('shows a question whose answer is null as a chip', () => {
    const { answers, chips } = itemQuestions(
      voteWith({
        suggested_questions: [
          'Wer war dagegen?',
          'Was kostet das?',
          'Wann gilt das?',
        ],
        suggested_answers: [
          null,
          { text: 'Nichts [1].', sources: [SOURCE] },
          null,
        ],
      }),
    );
    expect(answers.map((a) => [a.question, a.text])).toEqual([
      ['Was kostet das?', 'Nichts [0].'],
    ]);
    expect(chips).toEqual(['Wer war dagegen?', 'Wann gilt das?']);
  });

  it("keeps today's chips for an item without answers", () => {
    expect(
      itemQuestions(voteWith({ suggested_questions: ['Wer war dagegen?'] })),
    ).toEqual({ answers: [], chips: ['Wer war dagegen?'] });
  });
});

describe('toChatCitations', () => {
  it('counts from 0 and drops numbers without a source', () => {
    expect(toChatCitations('A [1][2]. B [1, 3]. C [5].', 2)).toBe(
      'A [0][1]. B [0]. C .',
    );
  });
});

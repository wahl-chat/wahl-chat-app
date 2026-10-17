import { describe, expect, it } from 'bun:test';
import type { DailyDigest } from '@/lib/firebase/firebase.types';
import { contextualQuestion, feedChatHref } from './chat-handoff';
import { sectionItems, voteItems } from './items';

const DIGEST: DailyDigest = {
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
      topics: ['health_care'],
      outcome: 'angenommen',
      citation_url: 'https://www.abgeordnetenwatch.de/poll/7',
      parties: [
        {
          party_id: 'afd',
          name: 'AfD',
          color: '',
          yes: 0,
          no: 1,
          abstain: 0,
          no_show: 0,
        },
        {
          party_id: 'fraktionslos',
          name: 'Fraktionslos',
          color: '',
          yes: 1,
          no: 0,
          abstain: 0,
          no_show: 0,
        },
        {
          party_id: 'spd',
          name: 'SPD',
          color: '',
          yes: 1,
          no: 0,
          abstain: 0,
          no_show: 0,
        },
      ],
    },
  ],
  session: {
    protocols: [{ protocol_id: '21/90', pdf_url: null }],
    sections: [
      {
        topic: 'economy_finance',
        headline: 'Haushalt 2027',
        summary: '',
        agenda_items: [],
        citations: [],
        video_url: null,
      },
    ],
    other_topics: [],
  },
};

describe('feedChatHref', () => {
  it('opens the parliament’s chat context with the vote’s parties', () => {
    const href = feedChatHref(voteItems(DIGEST)[0], 'Wer war dagegen?');
    const url = new URL(href, 'https://wahl.chat');
    expect(url.pathname).toBe('/bundestagswahl-2025/session');
    expect(url.searchParams.getAll('party_id')).toEqual(['spd', 'afd']);
    expect(url.searchParams.get('q')).toBe(
      'Zur Abstimmung „Stabile Kassenbeiträge“ im Bundestag am 10.07.2026 (Plenarprotokoll 21/90): Wer war dagegen?',
    );
  });

  it('cites the Plenarprotokoll for a debate', () => {
    expect(
      contextualQuestion(sectionItems(DIGEST)[0], ' Was kostet das? '),
    ).toBe(
      'Zur Debatte „Haushalt 2027“ im Bundestag am 10.07.2026 (Plenarprotokoll 21/90): Was kostet das?',
    );
  });
});

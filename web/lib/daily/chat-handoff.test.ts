import { describe, expect, it } from 'bun:test';
import type { DailyDigest } from '@/lib/firebase/firebase.types';
import { feedChatHref } from './chat-handoff';
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
      item_id: 'bundestag_2026-07-10_v7',
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
        item_id: 'bundestag_2026-07-10_d90-top17',
      },
    ],
  },
};

describe('feedChatHref', () => {
  it('opens the general chat with the question as typed and the vote as anchor', () => {
    const href = feedChatHref(voteItems(DIGEST)[0], 'Wer war dagegen?');
    const url = new URL(href, 'https://wahl.chat');
    expect(url.pathname).toBe('/chat');
    expect(url.searchParams.get('q')).toBe('Wer war dagegen?');
    expect(url.searchParams.get('feed_item')).toBe('bundestag_2026-07-10_v7');
    expect(url.searchParams.has('party_id')).toBe(false);
  });

  it('anchors a debate on its item', () => {
    const url = new URL(
      feedChatHref(sectionItems(DIGEST)[0], 'Was kostet das?'),
      'https://wahl.chat',
    );
    expect(url.searchParams.get('q')).toBe('Was kostet das?');
    expect(url.searchParams.get('feed_item')).toBe(
      'bundestag_2026-07-10_d90-top17',
    );
  });

  it('sends a local preview without an anchor', () => {
    const [vote] = voteItems({
      ...DIGEST,
      votes: [{ ...DIGEST.votes[0], item_id: undefined }],
    });
    const url = new URL(
      feedChatHref(vote, 'Warum?', 'why'),
      'https://wahl.chat',
    );
    expect(url.searchParams.has('feed_item')).toBe(false);
    expect(url.searchParams.has('preset')).toBe(false);
  });

  it('marks a button question; a typed one stays unmarked', () => {
    const [vote] = voteItems(DIGEST);
    const why = new URL(
      feedChatHref(vote, 'Warum?', 'why'),
      'https://wahl.chat',
    );
    expect(why.searchParams.get('preset')).toBe('why');
    const typed = new URL(feedChatHref(vote, 'Warum?'), 'https://wahl.chat');
    expect(typed.searchParams.has('preset')).toBe(false);
  });
});

import { describe, expect, it } from 'bun:test';
import type { FeedItem } from '@/lib/firebase/firebase.types';
import {
  anchorCard,
  chatAnchorFromParams,
  chatPresetFromParam,
  sanitizeChatAnchor,
} from './chat-anchor';

const VOTE_ITEM: FeedItem = {
  id: 'bundestag_2026-07-10_v7',
  kind: 'vote',
  edition_id: 'bundestag_2026-07-10',
  parliament: 'bundestag',
  parliament_name: 'Bundestag',
  region: 'DE',
  date: '2026-07-10',
  rank: 0,
  topics: ['health_care'],
  status: 'published',
  debate: null,
  vote: {
    poll_id: 7,
    official_title: 'Gesetzentwurf',
    outcome: 'angenommen',
    citation_url: null,
    description: null,
    parties: [],
  },
  content: {
    de: {
      headline: 'Stabile Kassenbeiträge',
      teaser: null,
      key_points: [],
      positions: [],
      suggested_questions: [],
      quote_translation: null,
      origin: 'generated',
    },
  },
};

describe('chatAnchorFromParams', () => {
  it('reads a feed item, which wins over a poll id', () => {
    expect(
      chatAnchorFromParams({
        feed_item: 'bundestag_2026-07-10_d90-top17',
        poll_id: '7',
      }),
    ).toEqual({ feed_item_id: 'bundestag_2026-07-10_d90-top17' });
  });

  it('reads a poll id as a number', () => {
    expect(chatAnchorFromParams({ poll_id: ['6402'] })).toEqual({
      poll_id: 6402,
    });
  });

  it('ignores malformed values', () => {
    expect(chatAnchorFromParams({})).toBeUndefined();
    expect(chatAnchorFromParams({ feed_item: '../x y' })).toBeUndefined();
    expect(chatAnchorFromParams({ poll_id: '-1' })).toBeUndefined();
    expect(chatAnchorFromParams({ poll_id: '0' })).toBeUndefined();
    expect(chatAnchorFromParams({ poll_id: '12abc' })).toBeUndefined();
  });
});

describe('sanitizeChatAnchor', () => {
  it('keeps exactly one well-formed key', () => {
    expect(
      sanitizeChatAnchor({ feed_item_id: 'bundestag_2026-07-10_v7', x: 1 }),
    ).toEqual({ feed_item_id: 'bundestag_2026-07-10_v7' });
    expect(sanitizeChatAnchor({ poll_id: 7 })).toEqual({ poll_id: 7 });
  });

  it('drops anything else', () => {
    expect(sanitizeChatAnchor(undefined)).toBeUndefined();
    expect(sanitizeChatAnchor('bundestag')).toBeUndefined();
    expect(sanitizeChatAnchor({ poll_id: 1.5 })).toBeUndefined();
    expect(sanitizeChatAnchor({ feed_item_id: 'a b' })).toBeUndefined();
  });
});

describe('anchorCard', () => {
  it('shows a vote item with kind, title, date, outcome and the way back', () => {
    expect(anchorCard({ feed_item_id: VOTE_ITEM.id }, VOTE_ITEM)).toEqual({
      kind: 'Abstimmung',
      title: 'Stabile Kassenbeiträge',
      date: '10. Juli 2026',
      outcome: 'angenommen',
      back: {
        itemId: 'bundestag_2026-07-10_v7',
        href: '/?item=bundestag_2026-07-10_v7&land=de',
        noun: 'Abstimmung',
      },
    });
  });

  it('calls a debate item a Debatte, without an outcome', () => {
    const card = anchorCard(
      { feed_item_id: 'd' },
      { ...VOTE_ITEM, id: 'd', kind: 'debate', vote: null },
    );
    expect(card?.kind).toBe('Debatte');
    expect(card?.outcome).toBeNull();
    expect(card?.back?.noun).toBe('Debatte');
  });

  it('shows nothing for a missing or retracted item', () => {
    expect(anchorCard({ feed_item_id: 'gone' }, null)).toBeNull();
    expect(
      anchorCard(
        { feed_item_id: VOTE_ITEM.id },
        { ...VOTE_ITEM, status: 'retracted' },
      ),
    ).toBeNull();
  });

  it('shows a bare poll id as a plain vote card', () => {
    expect(anchorCard({ poll_id: 6402 }, null)).toEqual({
      kind: 'Abstimmung',
      title: 'Abstimmung Nr. 6402',
      date: null,
      outcome: null,
      back: null,
    });
  });
});

describe('procedure anchors', () => {
  it('reads a procedure from the URL and keeps it when sanitized', () => {
    expect(chatAnchorFromParams({ procedure: '338366' })).toEqual({
      vorgang_id: '338366',
    });
    expect(sanitizeChatAnchor({ vorgang_id: '338366' })).toEqual({
      vorgang_id: '338366',
    });
    expect(chatAnchorFromParams({ procedure: '33x' })).toBeUndefined();
    expect(sanitizeChatAnchor({ vorgang_id: 338366 })).toBeUndefined();
  });

  it('shows the procedure with where it stands, once loaded', () => {
    const anchor = { vorgang_id: '338366' };
    expect(anchorCard(anchor, null, null)).toBeNull();
    expect(
      anchorCard(anchor, null, {
        vorgang_id: '338366',
        titel: 'Haushaltsbegleitgesetz 2027',
        latest_stage: 'Beschlussempfehlung und Bericht',
        latest_stage_on: '2026-11-16',
      }),
    ).toEqual({
      kind: 'Verfahren',
      title: 'Haushaltsbegleitgesetz 2027',
      date: 'Stand: Ausschuss: Empfehlung, 16. November 2026',
      outcome: null,
      back: null,
    });
  });

  it('names the third reading with the second and leads back to the item', () => {
    const card = anchorCard(
      { vorgang_id: '338341' },
      null,
      {
        vorgang_id: '338341',
        titel: 'Gesetz zur Reform des Nachrichtendienstrechts',
        latest_stage: '3. Beratung',
        latest_stage_on: '2026-11-13',
      },
      {
        id: 'bundestag_2026-11-13_v6771',
        region: 'DE',
        kind: 'vote',
        status: 'published',
      } as FeedItem,
    );
    expect(card?.date).toBe('Stand: 2./3. Lesung, 13. November 2026');
    expect(card?.back?.href).toContain('item=bundestag_2026-11-13_v6771');
    expect(card?.back?.noun).toBe('Abstimmung');
  });
});

describe('chatPresetFromParam', () => {
  it('keeps the two presets and drops anything else', () => {
    expect(chatPresetFromParam('why')).toBe('why');
    expect(chatPresetFromParam(['ask', 'why'])).toBe('ask');
    expect(chatPresetFromParam('cache')).toBeUndefined();
    expect(chatPresetFromParam(undefined)).toBeUndefined();
  });
});

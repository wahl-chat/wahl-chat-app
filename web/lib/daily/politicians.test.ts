import { describe, expect, it } from 'bun:test';
import type {
  DigestPartyPosition,
  Politician,
} from '@/lib/firebase/firebase.types';
import {
  displayName,
  gremienOf,
  mandateLabel,
  officeLines,
  speakerIds,
  speakerPhotos,
  tenureLabel,
} from './politicians';

const politician = (over: Partial<Politician>): Politician => ({
  mdb_id: '11005000',
  bio_id: '2314',
  title: null,
  first_name: 'Sanae',
  last_name: 'Abdi',
  name: 'Sanae Abdi',
  birth_date: '1986-07-07',
  fraktion: 'SPD',
  partei: 'SPD',
  beruf: 'Vertrags- und Finanzmanagerin',
  land: 'Nordrhein-Westfalen',
  wahlkreis: { number: '092', name: 'Köln I' },
  elected: 'direkt',
  offices: [],
  terms: [
    { wp: 20, start: '2021-10-26', end: '2025-03-25' },
    { wp: 21, start: '2025-03-25', end: null },
  ],
  memberships: [],
  disclosures: null,
  photo_url: null,
  photo_credit: null,
  bio_url: null,
  source_stand: null,
  last_changed: null,
  fetched_at: '2026-11-11T00:00:00Z',
  ...over,
});

const AWZ = 'Ausschuss für wirtschaftliche Zusammenarbeit und Entwicklung';

describe('gremienOf', () => {
  it('lists each committee once, under the most senior role held in it', () => {
    const rows = gremienOf(
      politician({
        memberships: [
          {
            gremium: 'Haushaltsausschuss',
            role: 'Stellvertretendes Mitglied',
            level: 'deputy',
            kind: 'ausschuss',
            url: null,
          },
          {
            gremium: AWZ,
            role: 'Ordentliches Mitglied',
            level: 'member',
            kind: 'ausschuss',
            url: null,
          },
          {
            gremium: AWZ,
            role: 'Obfrau',
            level: 'spokesperson',
            kind: 'ausschuss',
            url: null,
          },
          {
            gremium: 'Parlamentariergruppe Maghreb-Staaten',
            role: 'Stellvertretende Vorsitzende',
            level: 'vice_chair',
            kind: 'sonstige',
            url: null,
          },
        ],
      }),
      'ausschuss',
    );
    expect(rows.map((r) => [r.gremium, r.role])).toEqual([
      [AWZ, 'Obfrau'],
      ['Haushaltsausschuss', 'Stellvertretendes Mitglied'],
    ]);
  });
});

describe('labels', () => {
  it('counts the Wahlperioden from the first one', () => {
    expect(tenureLabel(politician({}))).toBe('2021 · 2 Wahlperioden');
    expect(
      tenureLabel(
        politician({ terms: [{ wp: 21, start: '2025-03-25', end: null }] }),
      ),
    ).toBe('2025 · 1 Wahlperiode');
    expect(tenureLabel(politician({ terms: [] }))).toBeNull();
  });

  it('names the Wahlkreis for a direct mandate, else the list', () => {
    expect(mandateLabel(politician({}))).toBe(
      'Direkt gewählt · Wahlkreis 092 – Köln I',
    );
    expect(mandateLabel(politician({ elected: 'Landesliste' }))).toBe(
      'Landesliste Nordrhein-Westfalen',
    );
    expect(mandateLabel(politician({ elected: null }))).toBeNull();
  });

  it('shows offices as published', () => {
    expect(
      officeLines(
        politician({
          offices: [
            {
              function: 'Bundesministerin',
              institution: 'Bundesministerium der Finanzen',
              kind: 'government',
            },
            {
              function: 'Vorstandsmitglied',
              institution: 'Fraktion der SPD',
              kind: 'fraktion',
            },
          ],
        }),
      ),
    ).toEqual([
      'Bundesministerin · Bundesministerium der Finanzen',
      'Vorstandsmitglied · Fraktion SPD',
    ]);
    expect(displayName(politician({ title: 'Dr.' }))).toBe('Dr. Sanae Abdi');
  });
});

describe('speakerIds', () => {
  it('collects every identified speaker once', () => {
    const party = (ids: (string | null)[]): DigestPartyPosition => ({
      party_id: 'spd',
      party_name: 'SPD',
      color: '#E3000F',
      position: null,
      speakers: ids.map((id, i) => ({ name: `n${i}`, url: null, mdb_id: id })),
    });
    expect(speakerIds([party(['1', null, '2']), party(['2', '3'])])).toEqual([
      '1',
      '2',
      '3',
    ]);
  });
});

describe('speakerPhotos', () => {
  it('maps each loaded speaker with a portrait to it', () => {
    expect(
      speakerPhotos({
        '1': politician({ mdb_id: '1', photo_url: 'https://x/1.jpg' }),
        '2': politician({ mdb_id: '2', photo_url: null }),
      }),
    ).toEqual({ '1': 'https://x/1.jpg' });
    expect(speakerPhotos(null)).toEqual({});
  });
});

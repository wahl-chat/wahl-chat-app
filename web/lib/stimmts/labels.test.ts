import { describe, expect, it } from 'bun:test';
import {
  dottedDate,
  monthShort,
  shortDay,
  submitterLine,
  timeAgo,
  weekdayName,
  yesMeaning,
} from './labels';
import type { BillDocument } from './types';

const DOCUMENT = {
  type: 'Antrag',
  number: '21/1234',
  date: '2026-06-08',
  title: 'Ein Antrag',
  url: 'https://dserver.bundestag.de/btd/21/012/2101234.pdf',
};

describe('dates', () => {
  it('writes the card and Drucksache forms', () => {
    expect(shortDay('2026-11-01')).toBe('So 1.11.');
    expect(dottedDate('2026-06-08')).toBe('08.06.2026');
    expect(weekdayName('2026-07-10')).toBe('Freitag');
    expect(monthShort('2026-07-10')).toBe('Jul');
  });

  it('says how long ago a vote was, from the puzzle day', () => {
    expect(timeAgo('2026-11-01', '2026-11-01')).toBe('heute');
    expect(timeAgo('2026-10-31', '2026-11-01')).toBe('gestern');
    expect(timeAgo('2026-10-25', '2026-11-01')).toBe('vor 7 Tagen');
    expect(timeAgo('2026-10-01', '2026-11-01')).toBe('vor 4 Wochen');
    expect(timeAgo('2026-07-10', '2026-11-01')).toBe('vor 4 Monaten');
    expect(timeAgo('2025-10-20', '2026-11-01')).toBe('vor einem Jahr');
  });
});

describe('yesMeaning', () => {
  it('drops the leading "Ja bedeutet:", which the key already says', () => {
    expect(
      yesMeaning(
        'Ja bedeutet: dem Gesetzentwurf der Bundesregierung zustimmen.',
      ),
    ).toBe('dem Gesetzentwurf der Bundesregierung zustimmen.');
    expect(yesMeaning('dem Antrag zustimmen.')).toBe('dem Antrag zustimmen.');
  });
});

describe('submitterLine', () => {
  it('prints an initiator as it is', () => {
    const document: BillDocument = {
      ...DOCUMENT,
      initiator: 'der Bundesregierung',
    };
    expect(submitterLine(document)).toBe('der Bundesregierung');
  });

  it('shortens a long list of members like the Bundestag does', () => {
    const document: BillDocument = {
      ...DOCUMENT,
      fraktion: 'der AfD',
      members: ['A. Peterka', 'B. Jacobi', 'C. Dritte', 'D. Vierte'],
    };
    expect(submitterLine(document)).toBe(
      'der Abgeordneten A. Peterka, B. Jacobi, weiterer Abgeordneter und der Fraktion der AfD',
    );
  });

  it('names two members in full', () => {
    const document: BillDocument = {
      ...DOCUMENT,
      fraktion: 'Die Linke',
      members: ['A. Erste', 'B. Zweite'],
    };
    expect(submitterLine(document)).toBe(
      'der Abgeordneten A. Erste, B. Zweite und der Fraktion Die Linke',
    );
  });
});

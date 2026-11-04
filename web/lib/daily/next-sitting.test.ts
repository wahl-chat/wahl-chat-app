import { describe, expect, it } from 'bun:test';
import type { SittingCalendar } from '@/lib/firebase/firebase.types';
import feedFixture from '../../../firebase/firestore_data/emulator/feed.json';
import {
  berlinToday,
  nextSitting,
  nextSittingText,
  weekRange,
} from './next-sitting';

const CALENDAR: SittingCalendar = {
  parliament: 'bundestag',
  weeks: [
    {
      start: '2026-11-02',
      end: '2026-11-06',
      sittings: [
        { date: '2026-11-04', number: 104 },
        { date: '2026-11-05', number: 105 },
        { date: '2026-11-06', number: 106 },
      ],
    },
    { start: '2026-11-09', end: '2026-11-13', sittings: null },
    { start: '2026-12-14', end: '2026-12-18', sittings: null },
    { start: '2027-01-11', end: '2027-01-15', sittings: null },
  ],
  sources: [],
  checked_at: '2026-11-04T05:00:00Z',
};

describe('nextSitting', () => {
  it('names the first sitting day of the week before it starts', () => {
    expect(nextSitting(CALENDAR, '2026-11-02')).toEqual({
      kind: 'day',
      date: '2026-11-04',
    });
  });

  it('says so on a sitting day', () => {
    expect(nextSitting(CALENDAR, '2026-11-05')).toEqual({ kind: 'today' });
  });

  it('moves on to the next week once the sittings are over', () => {
    expect(nextSitting(CALENDAR, '2026-11-07')).toEqual({
      kind: 'week',
      start: '2026-11-09',
      end: '2026-11-13',
    });
  });

  it('skips weeks that have passed while the stored copy ages', () => {
    expect(nextSitting(CALENDAR, '2026-11-20')).toEqual({
      kind: 'week',
      start: '2026-12-14',
      end: '2026-12-18',
    });
  });

  it('shows nothing without a calendar or past its last week', () => {
    expect(nextSitting(null, '2026-11-04')).toBeNull();
    expect(nextSitting(CALENDAR, '2027-02-01')).toBeNull();
  });

  it('reads the emulator seed', () => {
    const seeded = (feedFixture as { calendar: SittingCalendar }).calendar;
    expect(nextSitting(seeded, '2026-11-03')).toEqual({
      kind: 'day',
      date: '2026-11-04',
    });
  });
});

describe('nextSittingText', () => {
  it('writes a day with its weekday', () => {
    expect(
      nextSittingText({ kind: 'day', date: '2026-11-11' }, '2026-11-07'),
    ).toBe('Nächste Sitzung des Bundestages: Mittwoch, 11. November');
  });

  it('writes a week, with the year only when it is not this one', () => {
    expect(
      nextSittingText(
        { kind: 'week', start: '2026-11-09', end: '2026-11-13' },
        '2026-11-07',
      ),
    ).toBe('Nächste Sitzungswoche des Bundestages: 9.–13. November');
    expect(weekRange('2027-01-11', '2027-01-15', '2026-12-19')).toBe(
      '11.–15. Januar 2027',
    );
    expect(weekRange('2026-11-30', '2026-12-04', '2026-11-20')).toBe(
      '30. November – 4. Dezember',
    );
  });
});

describe('berlinToday', () => {
  it('uses Berlin time, not UTC', () => {
    // 23:30 UTC on 4 November is already 5 November in Berlin.
    expect(berlinToday(new Date('2026-11-04T23:30:00Z'))).toBe('2026-11-05');
  });
});

import { describe, expect, it } from 'bun:test';
import type { SittingCalendar } from '@/lib/firebase/firebase.types';
import feedFixture from '../../../firebase/firestore_data/emulator/feed.json';
import {
  berlinToday,
  calendarMonths,
  monthCells,
  shortRange,
  sittingStatus,
  upcomingSlots,
  waitingDays,
} from './sitting-calendar';

const days = (...dates: [string, number][]) =>
  dates.map(([date, number]) => ({ date, number }));

const CALENDAR: SittingCalendar = {
  parliament: 'bundestag',
  since: '2026-09-01',
  weeks: [
    {
      start: '2026-10-12',
      end: '2026-10-16',
      sittings: days(
        ['2026-10-14', 101],
        ['2026-10-15', 102],
        ['2026-10-16', 103],
      ),
    },
    {
      start: '2026-11-02',
      end: '2026-11-06',
      sittings: days(
        ['2026-11-04', 104],
        ['2026-11-05', 105],
        ['2026-11-06', 106],
      ),
    },
    { start: '2026-11-09', end: '2026-11-13', sittings: null },
    { start: '2026-11-30', end: '2026-12-04', sittings: null },
  ],
  sources: [],
  checked_at: '2026-11-05T05:00:00Z',
};

describe('sittingStatus', () => {
  it('says the parliament sits today, and when next', () => {
    expect(sittingStatus(CALENDAR, '2026-11-05')).toEqual({
      live: true,
      waiting: false,
      text: 'Tagt heute · nächste Sitzung Fr, 6. Nov.',
    });
  });

  it('names the next sitting day, or the week while its days are open', () => {
    expect(sittingStatus(CALENDAR, '2026-11-03')?.text).toBe(
      'Nächste Sitzung Mi, 4. Nov.',
    );
    expect(sittingStatus(CALENDAR, '2026-11-07')).toEqual({
      live: false,
      waiting: false,
      text: 'Nächste Sitzungswoche 9.–13. Nov.',
    });
  });

  it('has nothing to say without a calendar or past its last week', () => {
    expect(sittingStatus(null, '2026-11-05')).toBeNull();
    expect(sittingStatus(CALENDAR, '2026-12-05')).toBeNull();
  });
});

const WAITING = [
  { date: '2026-11-04', protocols: ['21/104'] },
  { date: '2026-11-05', protocols: ['21/105'] },
];

describe('waitingDays', () => {
  it('joins stored days without items to recent sittings without content', () => {
    expect(
      waitingDays(
        CALENDAR,
        ['2026-10-14', '2026-10-15', '2026-10-16', '2026-11-04'],
        [{ date: '2026-11-05', protocols: ['21/105'] }],
        '2026-11-07',
      ),
    ).toEqual([
      { date: '2026-11-05', protocols: ['21/105'] },
      { date: '2026-11-06', protocols: [] },
    ]);
  });

  it('leaves an old gap out, but never a stored day', () => {
    expect(
      waitingDays(
        CALENDAR,
        [],
        [{ date: '2026-10-15', protocols: ['21/102'] }],
        '2026-11-03',
      ).map((d) => d.date),
    ).toEqual(['2026-10-15']);
  });

  it('waits for nothing on the sitting day itself', () => {
    expect(waitingDays(CALENDAR, [], [], '2026-11-04')).toEqual([]);
  });
});

describe('days on their way into the feed', () => {
  it('lead the status line, with the next sitting', () => {
    expect(sittingStatus(CALENDAR, '2026-11-07', WAITING)).toEqual({
      live: false,
      waiting: true,
      text: '4.–5. Nov. in Arbeit · nächste Sitzungswoche 9.–13. Nov.',
    });
    expect(
      sittingStatus(CALENDAR, '2026-11-03', [
        { date: '2026-10-16', protocols: [] },
      ])?.text,
    ).toBe('16. Okt. in Arbeit · nächste Sitzung 4. Nov.');
  });

  it('give way to a sitting today', () => {
    const status = sittingStatus(CALENDAR, '2026-11-05', WAITING.slice(0, 1));
    expect(status?.live).toBe(true);
    expect(status?.waiting).toBe(false);
  });
});

describe('upcomingSlots', () => {
  it('skips past days and weeks', () => {
    expect(upcomingSlots(CALENDAR, '2026-11-06')[0]).toEqual({
      kind: 'day',
      date: '2026-11-06',
    });
    expect(shortRange('2026-11-30', '2026-12-04')).toBe('30. Nov. – 4. Dez.');
  });
});

describe('calendarMonths', () => {
  it('runs from when the feed begins to the last stored week', () => {
    expect(calendarMonths(CALENDAR, '2026-11-05')).toEqual([
      '2026-09',
      '2026-10',
      '2026-11',
      '2026-12',
    ]);
  });

  it('always includes today, even past the stored weeks', () => {
    expect(calendarMonths(CALENDAR, '2027-01-04').at(-1)).toBe('2027-01');
    expect(calendarMonths(null, '2026-11-05')).toEqual(['2026-11']);
  });
});

describe('monthCells', () => {
  const editions = ['2026-10-14', '2026-10-15', '2026-11-04', '2026-10-21'];
  const statusOf = (cells: ReturnType<typeof monthCells>, date: string) =>
    cells.find((c) => c?.date === date)?.status;

  it('starts the grid on Monday', () => {
    // November 2026 begins on a Sunday: six blanks.
    const cells = monthCells(CALENDAR, editions, '2026-11-05', '2026-11');
    expect(cells.slice(0, 7).map((c) => c?.day ?? null)).toEqual([
      null,
      null,
      null,
      null,
      null,
      null,
      1,
    ]);
    expect(cells.filter(Boolean)).toHaveLength(30);
  });

  it('colours each sitting day by what the feed holds', () => {
    const november = monthCells(CALENDAR, editions, '2026-11-05', '2026-11');
    expect(statusOf(november, '2026-11-04')).toBe('online');
    expect(statusOf(november, '2026-11-05')).toBe('today');
    expect(statusOf(november, '2026-11-06')).toBe('upcoming');
    expect(statusOf(november, '2026-11-02')).toBe('none');
    const october = monthCells(CALENDAR, editions, '2026-11-05', '2026-10');
    expect(statusOf(october, '2026-10-14')).toBe('online');
    expect(statusOf(october, '2026-10-16')).toBe('pending');
  });

  it('counts an edition outside the calendar as online', () => {
    const october = monthCells(CALENDAR, editions, '2026-11-05', '2026-10');
    expect(statusOf(october, '2026-10-21')).toBe('online');
  });

  it('marks days only where the exact date is known', () => {
    const november = monthCells(CALENDAR, editions, '2026-11-05', '2026-11');
    expect(statusOf(november, '2026-11-11')).toBe('none');
  });

  it('stays right while the stored copy ages', () => {
    // Read weeks later, the same copy turns its upcoming days into pending.
    const november = monthCells(CALENDAR, editions, '2026-11-20', '2026-11');
    expect(statusOf(november, '2026-11-05')).toBe('pending');
    expect(statusOf(november, '2026-11-06')).toBe('pending');
  });

  it('reads the emulator seed', () => {
    const seeded = (feedFixture as { calendar: SittingCalendar }).calendar;
    expect(seeded.since).toBe('2026-09-01');
    const cells = monthCells(seeded, [], '2026-11-05', '2026-11');
    expect(statusOf(cells, '2026-11-05')).toBe('today');
  });
});

describe('berlinToday', () => {
  it('uses Berlin time, not UTC', () => {
    // 23:30 UTC on 4 November is already 5 November in Berlin.
    expect(berlinToday(new Date('2026-11-04T23:30:00Z'))).toBe('2026-11-05');
  });
});

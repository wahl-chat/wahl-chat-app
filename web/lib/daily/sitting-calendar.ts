import type { SittingCalendar } from '@/lib/firebase/firebase.types';
import { FEED_WINDOW_DAYS, shiftDay } from './window';

/** Every date here is an ISO day, `YYYY-MM-DD`, in Berlin time. */

export const AGENDA_URL = 'https://www.bundestag.de/tagesordnung';

/** Today in Berlin, the calendar's own time zone. */
export function berlinToday(now: Date = new Date()): string {
  // en-CA formats as YYYY-MM-DD.
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Berlin',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(now);
}

function parts(day: string): { year: number; month: number; day: number } {
  const [year, month, date] = day.split('-').map(Number);
  return { year, month, day: date };
}

function utc(day: string): Date {
  return new Date(`${day}T00:00:00Z`);
}

/** 0 for Monday … 6 for Sunday. */
function weekday(day: string): number {
  return (utc(day).getUTCDay() + 6) % 7;
}

/** How the calendar writes its dates in one language. */
export type CalendarFormat = {
  /** "6. Nov." */
  shortDate: (day: string) => string;
  /** "Fr, 6. Nov." */
  shortDay: (day: string) => string;
  /** "9.–13. Nov.", or "30. Nov. – 4. Dez." across a month. */
  shortRange: (start: string, end: string) => string;
  /** "November 2026", from `YYYY-MM`. */
  monthLabel: (month: string) => string;
  /** The grid's column heads, Monday first: "Mo" … "So". */
  weekdays: string[];
};

/** `intl` is the BCP 47 tag of the reader's language (`LOCALE_INFO`). */
export function calendarFormat(intl: string): CalendarFormat {
  const date = new Intl.DateTimeFormat(intl, {
    day: 'numeric',
    month: 'short',
    timeZone: 'UTC',
  });
  // Engines differ on the abbreviation's full stop ("Fr" or "Fr."); the
  // calendar writes it without.
  const weekdayName = (d: Date) =>
    new Intl.DateTimeFormat(intl, { weekday: 'short', timeZone: 'UTC' })
      .format(d)
      .replace(/\.$/, '');
  const month = new Intl.DateTimeFormat(intl, {
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  });
  const shortDate = (day: string) => date.format(utc(day));
  return {
    shortDate,
    shortDay: (day) => `${weekdayName(utc(day))}, ${shortDate(day)}`,
    shortRange: (start, end) => date.formatRange(utc(start), utc(end)),
    monthLabel: (m) => month.format(utc(`${m}-01`)),
    // 2024-01-01 was a Monday.
    weekdays: Array.from({ length: 7 }, (_, i) =>
      weekdayName(utc(`2024-01-0${i + 1}`)),
    ),
  };
}

/** A known sitting day, or a whole sitting week whose days are not
 * published yet. */
export type Slot =
  | { kind: 'day'; date: string }
  | { kind: 'week'; start: string; end: string };

/** The sittings from `today` on, in order. The stored calendar runs weeks
 * ahead, so this is decided here, by the reader's date, and stays right
 * while the stored copy ages. */
export function upcomingSlots(
  calendar: SittingCalendar | null,
  today: string,
): Slot[] {
  return (calendar?.weeks ?? [])
    .filter((week) => week.end >= today)
    .flatMap((week): Slot[] =>
      week.sittings
        ? week.sittings
            .filter((s) => s.date >= today)
            .map((s) => ({ kind: 'day', date: s.date }))
        : [{ kind: 'week', start: week.start, end: week.end }],
    );
}

function sitsToday(slots: Slot[], today: string): boolean {
  return slots[0]?.kind === 'day' && slots[0].date === today;
}

/** A past sitting day the feed has no items for yet, with the protocols
 * known for it. */
export type WaitingDay = { date: string; protocols: string[] };

/**
 * The sitting days whose content is on its way, oldest first: every day the
 * builder stored without items yet, and every sitting day of the last
 * `FEED_WINDOW_DAYS` the feed holds nothing for, which the builder has not
 * reached yet. An older gap is not "bald", so it stays out.
 */
export function waitingDays(
  calendar: SittingCalendar | null,
  editionDates: readonly string[],
  waitingEditions: readonly WaitingDay[],
  today: string,
): WaitingDay[] {
  const online = new Set(editionDates);
  const since = shiftDay(today, -FEED_WINDOW_DAYS);
  const protocols = new Map<string, Set<string>>();
  for (const week of calendar?.weeks ?? []) {
    for (const { date } of week.sittings ?? []) {
      if (date >= since && date < today && !online.has(date)) {
        protocols.set(date, new Set());
      }
    }
  }
  for (const edition of waitingEditions) {
    const known = protocols.get(edition.date) ?? new Set();
    for (const id of edition.protocols) {
      known.add(id);
    }
    protocols.set(edition.date, known);
  }
  return [...protocols.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, ids]) => ({ date, protocols: [...ids] }));
}

/** "4.–5. Nov.", or "4. Nov." for one day. */
function waitingDates(
  waiting: readonly WaitingDay[],
  format: CalendarFormat,
): string {
  const first = waiting[0].date;
  const last = waiting[waiting.length - 1].date;
  return first === last
    ? format.shortDate(first)
    : format.shortRange(first, last);
}

/** The status line's sentences in the reader's language; each takes the
 * dates already written out. */
export type StatusWords = {
  /** "Tagt heute" */
  sitsToday: string;
  /** "Tagt heute · nächste Sitzung …" */
  sitsTodayThenNext: (when: string) => string;
  /** "4.–5. Nov. in Arbeit" */
  inProgress: (dates: string) => string;
  /** "nächste Sitzung …", after the days in progress. */
  nextDay: (date: string) => string;
  /** "nächste Sitzungswoche …", after the days in progress. */
  nextWeek: (range: string) => string;
  /** "Nächste Sitzung …", on its own. */
  nextDayAlone: (date: string) => string;
  /** "Nächste Sitzungswoche …", on its own. */
  nextWeekAlone: (range: string) => string;
};

export type SittingStatus = {
  live: boolean;
  /** Past sitting days are still on their way into the feed. */
  waiting: boolean;
  text: string;
};

/** The line under "Bundestag" in the parliament field. Today's sitting
 * outranks days still in the works. */
export function sittingStatus(
  calendar: SittingCalendar | null,
  today: string,
  waiting: readonly WaitingDay[],
  words: StatusWords,
  format: CalendarFormat,
): SittingStatus | null {
  const slots = upcomingSlots(calendar, today);
  const range = (slot: { start: string; end: string }) =>
    format.shortRange(slot.start, slot.end);
  if (sitsToday(slots, today)) {
    const after = slots[1];
    return {
      live: true,
      waiting: false,
      text: after
        ? words.sitsTodayThenNext(
            after.kind === 'day' ? format.shortDay(after.date) : range(after),
          )
        : words.sitsToday,
    };
  }
  const [next] = slots;
  if (waiting.length > 0) {
    const upcoming =
      next &&
      (next.kind === 'day'
        ? words.nextDay(format.shortDate(next.date))
        : words.nextWeek(range(next)));
    return {
      live: false,
      waiting: true,
      text: [words.inProgress(waitingDates(waiting, format)), upcoming]
        .filter(Boolean)
        .join(' · '),
    };
  }
  if (!next) {
    return null;
  }
  return {
    live: false,
    waiting: false,
    text:
      next.kind === 'day'
        ? words.nextDayAlone(format.shortDay(next.date))
        : words.nextWeekAlone(range(next)),
  };
}

/** `YYYY-MM` of a day. */
export function monthOf(day: string): string {
  return day.slice(0, 7);
}

function nextMonth(month: string): string {
  const { year, month: m } = parts(`${month}-01`);
  return m === 12
    ? `${year + 1}-01`
    : `${year}-${String(m + 1).padStart(2, '0')}`;
}

/** The months the grid can show: from when the feed begins to the last
 * stored week, today's month always among them. */
export function calendarMonths(
  calendar: SittingCalendar | null,
  today: string,
): string[] {
  if (!calendar) {
    return [monthOf(today)];
  }
  const ends = [
    monthOf(today),
    ...calendar.weeks.map((w) => monthOf(w.end)),
  ].sort();
  const first = [monthOf(calendar.since), monthOf(today)].sort()[0];
  const last = ends[ends.length - 1];
  const months: string[] = [];
  for (let m = first; m <= last; m = nextMonth(m)) {
    months.push(m);
  }
  return months;
}

/**
 * - online: content for the day is in the feed;
 * - today: the parliament sits today;
 * - pending: it sat, its content is not online yet;
 * - upcoming: it will sit;
 * - none: no sitting.
 */
export type DayStatus = 'online' | 'today' | 'pending' | 'upcoming' | 'none';

export type DayCell = {
  date: string;
  day: number;
  status: DayStatus;
  /** Its content is in the feed; today can be online and still 'today'. */
  online: boolean;
};

/** One month as a Monday-first grid: `null` for the blanks before the 1st.
 * A day counts as a sitting day only when its exact date is known, and as
 * online when the feed holds an edition for it, sitting day or not. */
export function monthCells(
  calendar: SittingCalendar | null,
  editionDates: readonly string[],
  today: string,
  month: string,
): (DayCell | null)[] {
  const sittings = new Set(
    (calendar?.weeks ?? []).flatMap((w) =>
      (w.sittings ?? []).map((s) => s.date),
    ),
  );
  const online = new Set(editionDates);
  const cells: (DayCell | null)[] = Array(weekday(`${month}-01`)).fill(null);
  for (let date = `${month}-01`; monthOf(date) === month; ) {
    const sits = sittings.has(date);
    let status: DayStatus = 'none';
    if (date === today && sits) {
      status = 'today';
    } else if (online.has(date)) {
      status = 'online';
    } else if (sits) {
      status = date < today ? 'pending' : 'upcoming';
    }
    cells.push({
      date,
      day: parts(date).day,
      status,
      online: online.has(date),
    });
    const next = new Date(`${date}T00:00:00Z`);
    next.setUTCDate(next.getUTCDate() + 1);
    date = next.toISOString().slice(0, 10);
  }
  return cells;
}

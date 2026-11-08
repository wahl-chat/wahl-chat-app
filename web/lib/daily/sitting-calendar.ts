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

const MONTHS = [
  'Januar',
  'Februar',
  'März',
  'April',
  'Mai',
  'Juni',
  'Juli',
  'August',
  'September',
  'Oktober',
  'November',
  'Dezember',
];
const MONTHS_SHORT = [
  'Jan.',
  'Feb.',
  'März',
  'Apr.',
  'Mai',
  'Juni',
  'Juli',
  'Aug.',
  'Sept.',
  'Okt.',
  'Nov.',
  'Dez.',
];
const WEEKDAYS_SHORT = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];

function parts(day: string): { year: number; month: number; day: number } {
  const [year, month, date] = day.split('-').map(Number);
  return { year, month, day: date };
}

/** 0 for Monday … 6 for Sunday. */
function weekday(day: string): number {
  return (new Date(`${day}T00:00:00Z`).getUTCDay() + 6) % 7;
}

/** "6. Nov." */
export function shortDate(day: string): string {
  const { month, day: date } = parts(day);
  return `${date}. ${MONTHS_SHORT[month - 1]}`;
}

/** "Fr, 6. Nov." */
export function shortDay(day: string): string {
  return `${WEEKDAYS_SHORT[weekday(day)]}, ${shortDate(day)}`;
}

/** "9.–13. Nov.", or "30. Nov. – 4. Dez." across a month. */
export function shortRange(start: string, end: string): string {
  const s = parts(start);
  const e = parts(end);
  return s.month === e.month
    ? `${s.day}.–${e.day}. ${MONTHS_SHORT[e.month - 1]}`
    : `${shortDate(start)} – ${shortDate(end)}`;
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

function slotDay(slot: Slot): string {
  return slot.kind === 'day'
    ? shortDay(slot.date)
    : shortRange(slot.start, slot.end);
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
function waitingDates(waiting: readonly WaitingDay[]): string {
  const first = waiting[0].date;
  const last = waiting[waiting.length - 1].date;
  return first === last ? shortDate(first) : shortRange(first, last);
}

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
  waiting: readonly WaitingDay[] = [],
): SittingStatus | null {
  const slots = upcomingSlots(calendar, today);
  if (sitsToday(slots, today)) {
    return {
      live: true,
      waiting: false,
      text: slots[1]
        ? `Tagt heute · nächste Sitzung ${slotDay(slots[1])}`
        : 'Tagt heute',
    };
  }
  const [next] = slots;
  if (waiting.length > 0) {
    const upcoming =
      next &&
      (next.kind === 'day'
        ? `nächste Sitzung ${shortDate(next.date)}`
        : `nächste Sitzungswoche ${shortRange(next.start, next.end)}`);
    return {
      live: false,
      waiting: true,
      text: [`${waitingDates(waiting)} in Arbeit`, upcoming]
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
        ? `Nächste Sitzung ${shortDay(next.date)}`
        : `Nächste Sitzungswoche ${shortRange(next.start, next.end)}`,
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

/** "November 2026" */
export function monthLabel(month: string): string {
  const { year, month: m } = parts(`${month}-01`);
  return `${MONTHS[m - 1]} ${year}`;
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

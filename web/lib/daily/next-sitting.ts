import type { SittingCalendar } from '@/lib/firebase/firebase.types';

export type NextSitting =
  | { kind: 'today' }
  | { kind: 'day'; date: string }
  | { kind: 'week'; start: string; end: string };

/** Today in Berlin as `YYYY-MM-DD`, the calendar's own time zone. */
export function berlinToday(now: Date = new Date()): string {
  // en-CA formats as YYYY-MM-DD.
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Berlin',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(now);
}

/**
 * The next time the parliament sits, from `today` on. The stored calendar
 * runs several weeks ahead, so the choice is made here, by the reader's date,
 * and stays right while the stored copy ages.
 */
export function nextSitting(
  calendar: SittingCalendar | null,
  today: string,
): NextSitting | null {
  for (const week of calendar?.weeks ?? []) {
    if (week.end < today) {
      continue;
    }
    if (!week.sittings) {
      return { kind: 'week', start: week.start, end: week.end };
    }
    if (week.sittings.some((s) => s.date === today)) {
      return { kind: 'today' };
    }
    const next = week.sittings.find((s) => s.date > today);
    if (next) {
      return { kind: 'day', date: next.date };
    }
  }
  return null;
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

const dayFormat = new Intl.DateTimeFormat('de-DE', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  timeZone: 'UTC',
});

function parts(isoDay: string): { year: number; month: number; day: number } {
  const [year, month, day] = isoDay.split('-').map(Number);
  return { year, month, day };
}

/** "9.–13. November", "30. November – 4. Dezember", with the year when it is
 * not this one. */
export function weekRange(start: string, end: string, today: string): string {
  const s = parts(start);
  const e = parts(end);
  const year = e.year === parts(today).year ? '' : ` ${e.year}`;
  if (s.month === e.month && s.year === e.year) {
    return `${s.day}.–${e.day}. ${MONTHS[e.month - 1]}${year}`;
  }
  return `${s.day}. ${MONTHS[s.month - 1]} – ${e.day}. ${MONTHS[e.month - 1]}${year}`;
}

export function nextSittingText(next: NextSitting, today: string): string {
  switch (next.kind) {
    case 'today':
      return 'Der Bundestag tagt heute. Die Debatten erscheinen hier, sobald das Protokoll vorliegt.';
    case 'day': {
      const year =
        parts(next.date).year === parts(today).year
          ? ''
          : ` ${parts(next.date).year}`;
      return `Nächste Sitzung des Bundestages: ${dayFormat.format(new Date(`${next.date}T00:00:00Z`))}${year}`;
    }
    case 'week':
      return `Nächste Sitzungswoche des Bundestages: ${weekRange(next.start, next.end, today)}`;
  }
}

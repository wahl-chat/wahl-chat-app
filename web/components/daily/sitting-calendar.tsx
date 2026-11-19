'use client';

import { LOCALE_INFO } from '@/i18n/locales';
import {
  AGENDA_URL,
  type CalendarFormat,
  type DayCell,
  type SittingStatus,
  type StatusWords,
  berlinToday,
  calendarFormat,
  calendarMonths,
  monthCells,
  monthOf,
} from '@/lib/daily/sitting-calendar';
import type { SittingCalendar } from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { ChevronLeftIcon, ChevronRightIcon, XIcon } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';
import { type TouchEvent, useMemo, useRef, useState } from 'react';
import { FOCUS_RING, MUTED_TEXT } from './card-styles';

// Written out, not interpolated: Tailwind only builds classes it reads in full.
const LIVE_DOT = 'bg-[#E53935]';
// A sideways swipe this long turns the month; shorter ones are taps.
const SWIPE_PX = 40;

/** The calendar's dates in the reader's language. */
export function useCalendarFormat(): CalendarFormat {
  const intl = LOCALE_INFO[useLocale()].intl;
  return useMemo(() => calendarFormat(intl), [intl]);
}

/** The status line's sentences in the reader's language. */
export function useStatusWords(): StatusWords {
  const t = useTranslations('feed.calendar');
  return {
    sitsToday: t('sitsToday'),
    sitsTodayThenNext: (when) => t('sitsTodayThenNext', { when }),
    inProgress: (dates) => t('inProgress', { dates }),
    nextDay: (date) => t('nextDay', { date }),
    nextWeek: (range) => t('nextWeek', { range }),
    nextDayAlone: (date) => t('nextDayAlone', { date }),
    nextWeekAlone: (range) => t('nextWeekAlone', { range }),
  };
}

/** A quarter-drawn ring: work under way, not a loading spinner. */
function ProgressRing() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      fill="none"
      strokeWidth={3}
      className="size-[11px] shrink-0"
    >
      <circle cx="12" cy="12" r="9" className="stroke-[var(--daily-border)]" />
      <path
        d="M21 12a9 9 0 0 0-9-9"
        strokeLinecap="round"
        className="stroke-[var(--daily-ink)]"
      />
    </svg>
  );
}

/** The line under "Bundestag" in the parliament field: a red dot while it
 * sits today, a ring while past sittings are on their way into the feed. */
export function SittingStatusLine({ status }: { status: SittingStatus }) {
  return (
    <span
      className={cn(
        'flex min-w-0 items-center gap-1.5 text-[12px]',
        MUTED_TEXT,
      )}
    >
      {status.waiting ? (
        <ProgressRing />
      ) : (
        <span
          aria-hidden
          className={cn(
            'size-1.5 shrink-0 rounded-full',
            status.live ? LIVE_DOT : 'bg-[var(--daily-muted)]',
          )}
        />
      )}
      <span className="truncate" suppressHydrationWarning>
        {status.text}
      </span>
    </span>
  );
}

const CELL_STYLE: Record<DayCell['status'], string> = {
  online:
    'bg-[var(--daily-day-online)] font-semibold text-[var(--daily-yes)] hover:brightness-95',
  today: 'bg-[var(--daily-ink)] font-bold text-[var(--daily-canvas)]',
  pending:
    'bg-[var(--daily-day-pending)] font-semibold text-[var(--daily-ink)] hover:bg-[var(--daily-day-pending-hover)]',
  upcoming:
    'border border-dashed border-[var(--daily-day-upcoming)] font-semibold text-[var(--daily-ink)] hover:bg-[var(--daily-surface)]',
  none: MUTED_TEXT,
};

const DOT_STYLE: Record<DayCell['status'], string> = {
  online: 'bg-[var(--daily-yes)]',
  today: LIVE_DOT,
  pending: 'bg-[var(--daily-muted)]',
  upcoming: 'bg-[var(--daily-ink)]',
  none: '',
};

/** What a tapped day without content to jump to says. */
function DayNote({
  cell,
  onClose,
}: {
  cell: DayCell;
  onClose: () => void;
}) {
  const t = useTranslations('feed.calendar');
  const day = useCalendarFormat().shortDay(cell.date);
  return (
    <div
      role="status"
      className="flex items-start gap-2 rounded-lg bg-[var(--daily-surface)] p-3 text-[13px] leading-snug"
    >
      <p className="flex-1">
        {cell.status === 'upcoming' ? (
          <>
            {t('plannedOn', { day })}{' '}
            <a
              href={AGENDA_URL}
              target="_blank"
              rel="noopener noreferrer"
              className={cn(FOCUS_RING, 'rounded underline underline-offset-2')}
            >
              {t('agenda')}
            </a>
          </>
        ) : (
          <>
            {cell.status === 'today'
              ? t('sitsTodayNote')
              : t('sittingOn', { day })}{' '}
            {t('contentFollows')}
          </>
        )}
      </p>
      <button
        type="button"
        aria-label={t('closeNote')}
        onClick={onClose}
        className={cn(
          FOCUS_RING,
          'flex size-6 shrink-0 items-center justify-center rounded-full hover:bg-[var(--daily-border)]',
          MUTED_TEXT,
        )}
      >
        <XIcon className="size-3.5" aria-hidden />
      </button>
    </div>
  );
}

const LEGEND: Exclude<DayCell['status'], 'none'>[] = [
  'online',
  'today',
  'pending',
  'upcoming',
];

function Legend() {
  const t = useTranslations('feed.calendar.legend');
  return (
    <ul
      className={cn(
        'flex flex-wrap justify-center gap-x-4 gap-y-1.5 text-[13px]',
        MUTED_TEXT,
      )}
    >
      {LEGEND.map((status) => (
        <li key={status} className="flex items-center gap-1.5">
          <span
            aria-hidden
            className={cn('size-3.5 rounded-[4px]', CELL_STYLE[status])}
          />
          {t(status)}
        </li>
      ))}
    </ul>
  );
}

/**
 * The Bundestag's sitting days as a month grid that reaches back to when the
 * feed begins. Every date comes from the stored calendar (bundestag.de) and
 * the stored feed editions.
 */
export function SittingCalendarPanel({
  calendar,
  editionDates,
  onJumpToDay,
}: {
  calendar: SittingCalendar;
  editionDates: readonly string[];
  /** A day whose content is online: show it in the feed. */
  onJumpToDay: (date: string) => void;
}) {
  const t = useTranslations('feed.calendar');
  const format = useCalendarFormat();
  const [today] = useState(berlinToday);
  const months = calendarMonths(calendar, today);
  const [month, setMonth] = useState(() => monthOf(today));
  const [note, setNote] = useState<DayCell | null>(null);
  const touchX = useRef<number | null>(null);
  const index = months.indexOf(month);

  const turn = (step: number) => {
    const next = months[index + step];
    if (next) {
      setMonth(next);
      setNote(null);
    }
  };
  const tap = (cell: DayCell) => {
    if (cell.online) {
      onJumpToDay(cell.date);
    } else {
      setNote(note?.date === cell.date ? null : cell);
    }
  };
  const swipeStart = (event: TouchEvent) => {
    touchX.current = event.touches[0]?.clientX ?? null;
  };
  const swipeEnd = (event: TouchEvent) => {
    const start = touchX.current;
    const end = event.changedTouches[0]?.clientX;
    touchX.current = null;
    if (
      start !== null &&
      end !== undefined &&
      Math.abs(end - start) > SWIPE_PX
    ) {
      turn(end < start ? 1 : -1);
    }
  };

  return (
    <section
      aria-label={t('label')}
      className="flex flex-col gap-3"
      suppressHydrationWarning
    >
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between">
          <button
            type="button"
            aria-label={t('previousMonth')}
            disabled={index <= 0}
            onClick={() => turn(-1)}
            className={cn(
              FOCUS_RING,
              'flex size-8 items-center justify-center rounded-full hover:bg-[var(--daily-surface)] disabled:opacity-30',
            )}
          >
            <ChevronLeftIcon className="size-4" aria-hidden />
          </button>
          <span className={cn('text-[12px] font-semibold', MUTED_TEXT)}>
            {format.monthLabel(month)}
          </span>
          <button
            type="button"
            aria-label={t('nextMonth')}
            disabled={index >= months.length - 1}
            onClick={() => turn(1)}
            className={cn(
              FOCUS_RING,
              'flex size-8 items-center justify-center rounded-full hover:bg-[var(--daily-surface)] disabled:opacity-30',
            )}
          >
            <ChevronRightIcon className="size-4" aria-hidden />
          </button>
        </div>
        <div
          role="grid"
          aria-label={t('monthLabel', { month: format.monthLabel(month) })}
          onTouchStart={swipeStart}
          onTouchEnd={swipeEnd}
          className="grid touch-pan-y grid-cols-7 gap-x-1 gap-y-0.5"
        >
          {format.weekdays.map((day) => (
            <span
              key={day}
              className={cn('text-center text-[10px]', MUTED_TEXT)}
            >
              {day}
            </span>
          ))}
          {monthCells(calendar, editionDates, today, month).map((cell, i) =>
            cell === null ? (
              // biome-ignore lint/suspicious/noArrayIndexKey: blanks before the 1st
              <span key={`blank-${i}`} />
            ) : cell.status === 'none' ? (
              <span
                key={cell.date}
                className={cn(
                  'flex h-8 items-center justify-center text-[12px]',
                  CELL_STYLE.none,
                  cell.date === today && 'font-bold text-[var(--daily-ink)]',
                )}
              >
                {cell.day}
              </span>
            ) : (
              <button
                key={cell.date}
                type="button"
                aria-label={`${format.shortDay(cell.date)}: ${t(`cell.${cell.status}`)}`}
                aria-pressed={note?.date === cell.date}
                onClick={() => tap(cell)}
                className={cn(
                  FOCUS_RING,
                  'relative flex h-8 items-center justify-center rounded-md text-[12px] transition-colors',
                  CELL_STYLE[cell.status],
                )}
              >
                {cell.day}
                <span
                  aria-hidden
                  className={cn(
                    'absolute bottom-0.5 left-1/2 size-[3px] -translate-x-1/2 rounded-full',
                    DOT_STYLE[cell.status],
                  )}
                />
              </button>
            ),
          )}
        </div>
        <Legend />
      </div>
      {note && <DayNote cell={note} onClose={() => setNote(null)} />}
    </section>
  );
}

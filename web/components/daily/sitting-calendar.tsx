'use client';

import {
  AGENDA_URL,
  type DayCell,
  type SittingStatus,
  type SittingTile,
  berlinToday,
  calendarMonths,
  monthCells,
  monthLabel,
  monthOf,
  shortDay,
  sittingTiles,
} from '@/lib/daily/sitting-calendar';
import type { SittingCalendar } from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { ChevronLeftIcon, ChevronRightIcon, XIcon } from 'lucide-react';
import { type TouchEvent, useRef, useState } from 'react';
import { FOCUS_RING, MUTED_TEXT } from './card-styles';

// Written out, not interpolated: Tailwind only builds classes it reads in full.
const LIVE_DOT = 'bg-[#E53935]';
const LIVE_TEXT = 'text-[#B3261E] dark:text-[#FF8A80]';
const WEEKDAYS = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];
// A sideways swipe this long turns the month; shorter ones are taps.
const SWIPE_PX = 40;

/** The line under "Bundestag" in the parliament field: a red dot while it
 * sits today. */
export function SittingStatusLine({ status }: { status: SittingStatus }) {
  return (
    <span
      className={cn(
        'flex min-w-0 items-center gap-1.5 text-[12px]',
        MUTED_TEXT,
      )}
    >
      <span
        aria-hidden
        className={cn(
          'size-1.5 shrink-0 rounded-full',
          status.live ? LIVE_DOT : 'bg-[var(--daily-muted)]',
        )}
      />
      <span className="truncate" suppressHydrationWarning>
        {status.text}
      </span>
    </span>
  );
}

function Tile({ tile }: { tile: SittingTile }) {
  return (
    <div
      className={cn(
        'flex min-w-0 flex-1 flex-col gap-px rounded-lg px-2.5 py-2',
        tile.live ? 'bg-[rgb(229_57_53_/_0.1)]' : 'bg-[var(--daily-surface)]',
      )}
    >
      <span
        className={cn(
          'flex items-center gap-1.5 text-[11px] font-semibold',
          tile.live ? LIVE_TEXT : MUTED_TEXT,
        )}
      >
        {tile.live && (
          <span
            aria-hidden
            className={cn(
              'size-2 rounded-full shadow-[0_0_0_3px_rgb(229_57_53_/_0.18)]',
              LIVE_DOT,
            )}
          />
        )}
        {tile.label}
      </span>
      <span className="truncate text-[13px] font-semibold">{tile.date}</span>
      {tile.agenda ? (
        <a
          href={AGENDA_URL}
          target="_blank"
          rel="noopener noreferrer"
          className={cn(FOCUS_RING, 'w-fit rounded text-[11px]', MUTED_TEXT)}
        >
          Tagesordnung →
        </a>
      ) : (
        tile.after && (
          <span className={cn('text-[11px]', MUTED_TEXT)}>{tile.after}</span>
        )
      )}
    </div>
  );
}

const CELL_STYLE: Record<DayCell['status'], string> = {
  online:
    'bg-[var(--daily-yes-bg)] font-semibold text-[var(--daily-yes)] hover:brightness-95',
  today: 'bg-[var(--daily-ink)] font-bold text-[var(--daily-canvas)]',
  pending:
    'bg-[var(--daily-surface)] font-semibold text-[var(--daily-ink)] hover:bg-[var(--daily-border)]',
  upcoming:
    'border border-[var(--daily-border)] font-semibold text-[var(--daily-ink)] hover:bg-[var(--daily-surface)]',
  none: MUTED_TEXT,
};

const DOT_STYLE: Record<DayCell['status'], string> = {
  online: 'bg-[var(--daily-yes)]',
  today: LIVE_DOT,
  pending: 'bg-[var(--daily-muted)]',
  upcoming: 'bg-[var(--daily-ink)]',
  none: '',
};

const CELL_LABEL: Record<DayCell['status'], string> = {
  online: 'Sitzungstag, Inhalte online',
  today: 'Sitzungstag heute',
  pending: 'Sitzungstag, Inhalte noch nicht online',
  upcoming: 'Sitzungstag geplant',
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
  const day = shortDay(cell.date);
  return (
    <div
      role="status"
      className="flex items-start gap-2 rounded-lg bg-[var(--daily-surface)] p-3 text-[13px] leading-snug"
    >
      <p className="flex-1">
        {cell.status === 'upcoming' ? (
          <>
            Sitzung am {day} geplant.{' '}
            <a
              href={AGENDA_URL}
              target="_blank"
              rel="noopener noreferrer"
              className={cn(FOCUS_RING, 'rounded underline underline-offset-2')}
            >
              Tagesordnung
            </a>
          </>
        ) : (
          <>
            {cell.status === 'today'
              ? 'Der Bundestag tagt heute.'
              : `Sitzung am ${day}:`}{' '}
            Die Inhalte erscheinen hier, sobald das Plenarprotokoll online ist.
          </>
        )}
      </p>
      <button
        type="button"
        aria-label="Hinweis schließen"
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

function Legend() {
  const items: [DayCell['status'], string][] = [
    ['online', 'online'],
    ['today', 'heute'],
    ['pending', 'folgt'],
    ['upcoming', 'geplant'],
  ];
  return (
    <ul
      className={cn('flex flex-wrap gap-x-3 gap-y-1 text-[11px]', MUTED_TEXT)}
    >
      {items.map(([status, label]) => (
        <li key={status} className="flex items-center gap-1">
          <span
            aria-hidden
            className={cn('size-2.5 rounded-[3px]', CELL_STYLE[status])}
          />
          {label}
        </li>
      ))}
    </ul>
  );
}

/**
 * The Bundestag's sitting days: the next two sittings, then a month grid
 * that reaches back to when the feed begins. Every date comes from the
 * stored calendar (bundestag.de) and the stored feed editions.
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
  const [today] = useState(berlinToday);
  const months = calendarMonths(calendar, today);
  const [month, setMonth] = useState(() => monthOf(today));
  const [note, setNote] = useState<DayCell | null>(null);
  const touchX = useRef<number | null>(null);
  const index = months.indexOf(month);
  const tiles = sittingTiles(calendar, today);

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
      aria-label="Sitzungstage des Bundestages"
      className="flex flex-col gap-3"
      suppressHydrationWarning
    >
      {tiles.length > 0 && (
        <div className="flex gap-2">
          {tiles.map((tile) => (
            <Tile key={tile.label} tile={tile} />
          ))}
        </div>
      )}
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between">
          <button
            type="button"
            aria-label="Vorheriger Monat"
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
            {monthLabel(month)}
          </span>
          <button
            type="button"
            aria-label="Nächster Monat"
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
          aria-label={`Sitzungstage ${monthLabel(month)}`}
          onTouchStart={swipeStart}
          onTouchEnd={swipeEnd}
          className="grid touch-pan-y grid-cols-7 gap-x-1 gap-y-0.5"
        >
          {WEEKDAYS.map((day) => (
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
                aria-label={`${shortDay(cell.date)}: ${CELL_LABEL[cell.status]}`}
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

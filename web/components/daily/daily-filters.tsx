'use client';

import { Checkbox } from '@/components/ui/checkbox';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { DAILY_THEME_CLASSES } from '@/lib/daily/fonts';
import {
  BUNDESTAG,
  DAILY_STATES,
  DEFAULT_SELECTION,
  type StateSelection,
  selectionName,
  sigilFor,
} from '@/lib/daily/region';
import {
  type SittingStatus,
  type WaitingDay,
  berlinToday,
  sittingStatus,
  waitingDays,
} from '@/lib/daily/sitting-calendar';
import { DAILY_TOPIC_KEYS } from '@/lib/daily/topics';
import type { SittingCalendar } from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { ChevronDownIcon } from 'lucide-react';
import Image from 'next/image';
import { type RefObject, useEffect, useRef, useState } from 'react';
import { FOCUS_RING, MUTED_TEXT, PILL, PILL_ACTIVE } from './card-styles';
import { ScrollRow, pageStep } from './scroll-row';
import { SittingCalendarPanel, SittingStatusLine } from './sitting-calendar';
import TopicChip from './topic-chip';

const CHECKBOX =
  'size-5 rounded-[4px] border-zinc-400 data-[state=checked]:border-zinc-900 data-[state=checked]:bg-zinc-900 data-[state=checked]:text-white';

const ROW = 'flex min-h-11 items-center gap-4 px-4';

const ORDER = [BUNDESTAG, ...Object.keys(DAILY_STATES)];

function inListOrder(codes: StateSelection): StateSelection {
  return [...codes].sort((a, b) => ORDER.indexOf(a) - ORDER.indexOf(b));
}

function Sigil({ code, label }: { code: string; label?: boolean }) {
  const src = sigilFor(code);
  return src ? (
    <Image
      src={src}
      alt={label ? selectionName(code) : ''}
      width={24}
      height={24}
      className="size-6 object-contain"
    />
  ) : null;
}

/** One parliament: its coat of arms and name. Several: the coats of arms
 * alone, side by side, which read faster than a list of names. Under either,
 * when the Bundestag sits next. */
function SelectionSummary({
  states,
  status,
}: {
  states: StateSelection;
  status: SittingStatus | null;
}) {
  const line = status && <SittingStatusLine status={status} />;
  if (states.length === 1) {
    return (
      <span className="flex min-w-0 items-center gap-3">
        <Sigil code={states[0]} />
        <span className="flex min-w-0 flex-col">
          <span className="truncate text-[17px] font-semibold leading-tight">
            {selectionName(states[0])}
          </span>
          {line}
        </span>
      </span>
    );
  }
  return (
    <span className="flex min-w-0 flex-col gap-0.5">
      <span className="flex items-center gap-2">
        {states.map((code) => (
          <Sigil key={code} code={code} label />
        ))}
      </span>
      {line}
    </span>
  );
}

/** The Landtage, folded away behind "kommt bald" while none is covered, so
 * the panel leads with the Bundestag and its calendar. */
function LandtageList({
  draft,
  onToggle,
}: {
  draft: StateSelection;
  onToggle: (code: string, checked: boolean) => void;
}) {
  const states = Object.entries(DAILY_STATES);
  const anyCovered = states.some(([, state]) => state.parliament !== undefined);
  const [expanded, setExpanded] = useState(anyCovered);
  return (
    <fieldset className="py-2">
      <legend className="sr-only">Landtage</legend>
      <button
        type="button"
        aria-expanded={expanded}
        aria-controls="parliament-landtage"
        onClick={() => setExpanded((open) => !open)}
        className={cn(FOCUS_RING, ROW, 'w-full text-left text-[15px]')}
      >
        <span className="flex-1 font-semibold">Landtage</span>
        {!anyCovered && (
          <span
            className={cn(
              'rounded-full bg-[var(--daily-surface)] px-2.5 py-0.5 text-[13px]',
              MUTED_TEXT,
            )}
          >
            kommt bald
          </span>
        )}
        <ChevronDownIcon
          aria-hidden
          className={cn(
            'size-4 shrink-0 transition-transform',
            expanded && 'rotate-180',
          )}
        />
      </button>
      <div id="parliament-landtage" hidden={!expanded}>
        {states.map(([code, state]) => {
          const covered = state.parliament !== undefined;
          return (
            <div key={code} className={ROW}>
              <Checkbox
                id={`parliament-${code}`}
                className={CHECKBOX}
                checked={draft.includes(code)}
                disabled={!covered}
                onCheckedChange={(checked) => onToggle(code, checked === true)}
              />
              <label
                htmlFor={`parliament-${code}`}
                className={cn(
                  'flex flex-1 items-center self-stretch text-[15px]',
                  !covered && cn('cursor-not-allowed', MUTED_TEXT),
                )}
              >
                {state.name}
              </label>
            </div>
          );
        })}
      </div>
    </fieldset>
  );
}

/**
 * The Bundestag and any covered Landtage, chosen in a panel that drops down
 * under the box. Changes are staged and only applied on "Fertig", so the feed
 * does not reshuffle on every tick. The Bundestag is the default; at least
 * one parliament must stay selected. The box says when the Bundestag sits
 * next; the panel shows its sitting days.
 */
export function ParliamentSelector({
  states,
  onChange,
  calendar = null,
  editionDates = [],
  waitingEditions = [],
  onJumpToDay,
}: {
  states: StateSelection;
  onChange: (states: StateSelection) => void;
  calendar?: SittingCalendar | null;
  editionDates?: readonly string[];
  /** Bundestag days stored before any of their items. */
  waitingEditions?: readonly WaitingDay[];
  /** A sitting day whose content is online was chosen in the calendar. */
  onJumpToDay?: (date: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(states);
  const [today] = useState(berlinToday);
  // Closing for a jump into the feed: focus goes to the day, not back here.
  const jumping = useRef(false);
  const waiting = waitingDays(calendar, editionDates, waitingEditions, today);
  const status = states.includes(BUNDESTAG)
    ? sittingStatus(calendar, today, waiting)
    : null;

  const openChange = (next: boolean) => {
    setDraft(states);
    setOpen(next);
  };
  const toggle = (code: string, checked: boolean) =>
    setDraft((current) =>
      inListOrder(
        checked ? [...current, code] : current.filter((c) => c !== code),
      ),
    );

  return (
    <Popover open={open} onOpenChange={openChange}>
      {/* Dims the feed behind the panel while leaving it visible. */}
      {open && (
        <div
          aria-hidden
          className="fixed inset-x-0 bottom-0 top-[var(--header-height)] z-20 bg-white/60 dark:bg-black/50"
        />
      )}
      <PopoverTrigger
        aria-label={`Parlament wählen, gewählt: ${states.map(selectionName).join(', ')}`}
        className={cn(
          FOCUS_RING,
          'relative z-[25] flex min-h-14 w-full items-center gap-3 rounded-[10px] border bg-[var(--daily-canvas)] px-4 py-2 text-left',
          open ? 'border-[var(--daily-ink)]' : 'border-[var(--daily-border)]',
        )}
      >
        <SelectionSummary states={states} status={status} />
        {/* On a phone the sitting status needs the room; the chevron still
            says the box opens. */}
        <span
          className={cn(
            'ml-auto shrink-0 text-[15px]',
            status && 'hidden sm:inline',
            MUTED_TEXT,
          )}
        >
          {open ? `${draft.length} gewählt` : 'Parlament wählen'}
        </span>
        <ChevronDownIcon
          aria-hidden
          className={cn(
            'size-4 shrink-0 transition-transform',
            status && 'ml-auto sm:ml-0',
            open && 'rotate-180',
          )}
        />
      </PopoverTrigger>
      <PopoverContent
        align="start"
        sideOffset={2}
        onCloseAutoFocus={(event) => {
          if (jumping.current) {
            event.preventDefault();
            jumping.current = false;
          }
        }}
        className={cn(
          DAILY_THEME_CLASSES,
          'flex max-h-[min(70dvh,36rem)] w-[var(--radix-popover-trigger-width)] flex-col overflow-hidden rounded-xl border-[var(--daily-border)] p-0 shadow-xl',
        )}
      >
        <div className={cn(ROW, 'border-b border-[var(--daily-border)] py-2')}>
          <Checkbox
            id="parliament-bundestag"
            className={CHECKBOX}
            checked={draft.includes(BUNDESTAG)}
            onCheckedChange={(checked) => toggle(BUNDESTAG, checked === true)}
          />
          <label
            htmlFor="parliament-bundestag"
            className="flex-1 text-[17px] font-semibold"
          >
            Bundestag
          </label>
          <span className="rounded-full bg-[var(--daily-surface)] px-2.5 py-0.5 text-[13px]">
            Standard
          </span>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {calendar && (
            <div className="border-b border-[var(--daily-border)] px-4 py-3">
              <SittingCalendarPanel
                calendar={calendar}
                editionDates={editionDates}
                onJumpToDay={(date) => {
                  jumping.current = true;
                  setOpen(false);
                  onJumpToDay?.(date);
                }}
              />
            </div>
          )}
          <LandtageList draft={draft} onToggle={toggle} />
        </div>
        <div className="flex items-center justify-between border-t border-[var(--daily-border)] p-3">
          <button
            type="button"
            onClick={() => setDraft(DEFAULT_SELECTION)}
            className={cn(
              FOCUS_RING,
              'min-h-10 rounded-lg px-1 text-[15px]',
              MUTED_TEXT,
            )}
          >
            Zurücksetzen
          </button>
          {draft.length === 0 && (
            <span className={cn('text-[13px]', MUTED_TEXT)}>
              Mindestens eins wählen
            </span>
          )}
          <button
            type="button"
            disabled={draft.length === 0}
            onClick={() => {
              onChange(draft);
              setOpen(false);
            }}
            className={cn(
              FOCUS_RING,
              'min-h-11 rounded-lg bg-[var(--daily-ink)] px-5 text-[15px] font-semibold text-[var(--daily-canvas)] disabled:opacity-40',
            )}
          >
            Fertig
          </button>
        </div>
      </PopoverContent>
    </Popover>
  );
}

/** Whether the sticky element has reached its stuck position under the
 * header, so it can draw the line that separates it from the feed below. */
function useStuck(ref: RefObject<HTMLElement | null>): boolean {
  const [stuck, setStuck] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) {
      return;
    }
    let frame = 0;
    const check = () => {
      frame = 0;
      const top = Number.parseFloat(getComputedStyle(el).top) || 0;
      setStuck(
        window.scrollY > 0 && el.getBoundingClientRect().top <= top + 0.5,
      );
    };
    const onScroll = () => {
      if (!frame) {
        frame = requestAnimationFrame(check);
      }
    };
    check();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', onScroll);
      cancelAnimationFrame(frame);
    };
  }, [ref]);
  return stuck;
}

/** "Alle Themen" plus one pill per topic, in one sideways-scrolling row that
 * stays under the header while the feed scrolls. */
export function TopicPills({
  topics,
  onChange,
}: {
  topics: string[];
  onChange: (topics: string[]) => void;
}) {
  const toggle = (topic: string) =>
    onChange(
      topics.includes(topic)
        ? topics.filter((t) => t !== topic)
        : [...topics, topic],
    );

  const bar = useRef<HTMLFieldSetElement>(null);
  const stuck = useStuck(bar);

  return (
    // Below the parliament panel's backdrop (z-20), so an open panel dims it
    // like the rest of the feed.
    <fieldset
      ref={bar}
      className={cn(
        'sticky top-[var(--header-height)] z-[15] -mx-4 h-14 min-w-0 border-b bg-[var(--daily-canvas)] py-2',
        stuck ? 'border-[var(--daily-border)]' : 'border-transparent',
      )}
    >
      <legend className="sr-only">Themen</legend>
      <ScrollRow label="Themen" step={pageStep} bleed={false} className="gap-2">
        <button
          type="button"
          aria-pressed={topics.length === 0}
          onClick={() => onChange([])}
          className={cn(PILL, FOCUS_RING, topics.length === 0 && PILL_ACTIVE)}
        >
          Alle Themen
        </button>
        {DAILY_TOPIC_KEYS.map((topic) => (
          <TopicChip
            key={topic}
            topic={topic}
            active={topics.includes(topic)}
            onClick={() => toggle(topic)}
          />
        ))}
      </ScrollRow>
    </fieldset>
  );
}

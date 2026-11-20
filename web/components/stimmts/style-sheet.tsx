'use client';

import { FOCUS_RING } from '@/components/daily/card-styles';
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerTitle,
} from '@/components/ui/drawer';
import { berlinMonth } from '@/lib/stimmts/berlin-time';
import {
  type SheetState,
  barFill,
  barLabel,
  confirmedStyle,
  gridColumns,
  isLocked,
  milestoneMarks,
  nextIndex,
  openSheet,
  selectStyle,
  styleName,
  thumbLabel,
  thumbSubline,
} from '@/lib/stimmts/style-sheet-view';
import { styleStore, useStimmtsStyle } from '@/lib/stimmts/style-store';
import { STYLE_THEMES } from '@/lib/stimmts/style-themes';
import { type StyleId, visibleStyles } from '@/lib/stimmts/styles';
import { cn } from '@/lib/utils';
import { Lock, X } from 'lucide-react';
import { type KeyboardEvent, useEffect, useRef, useState } from 'react';

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

/** Standard keeps the site's own look, so its thumb is the plain card. */
const STANDARD_THUMB = {
  canvas: '#ffffff',
  border: '#e4e4e7',
  ink: '#18181b',
  muted: '#e4e4e7',
} as const;

const GOLD_ACCENT = '#c9a85c';
const GOLD_RING =
  'inset 0 0 0 3px #12100b, inset 0 0 0 5px #c9a85c, inset 0 0 0 7px #12100b, inset 0 0 0 8px rgba(201,168,92,0.6)';

function thumbColours(id: StyleId) {
  if (id === 'standard') {
    return STANDARD_THUMB;
  }
  const theme = STYLE_THEMES[id];
  return {
    canvas: theme.canvas,
    border: theme.border,
    ink: theme.ink,
    muted: theme.border,
  };
}

/** A few marks of each style's decoration, enough to tell the thumbs apart. */
function ThumbDecor({ id }: { id: StyleId }) {
  switch (id) {
    case 'papier':
      return (
        <span
          aria-hidden
          className="absolute inset-0"
          style={{
            backgroundImage:
              'radial-gradient(rgba(110,80,30,0.3) 0.8px, transparent 1.2px)',
            backgroundSize: '4px 4px',
          }}
        />
      );
    case 'kuppel':
      return (
        <svg
          aria-hidden
          className="absolute bottom-1 left-1/2 -ml-[30px]"
          width="60"
          height="38"
          viewBox="0 0 300 190"
          fill="none"
          stroke="#7f9ab3"
          strokeWidth="9"
          strokeLinecap="round"
        >
          <path d="M30 170 C30 92 88 38 150 38 C212 38 270 92 270 170 M150 38 V170 M150 38 C118 58 92 110 88 170 M150 38 C182 58 208 110 212 170 M62 98 Q150 114 238 98 M10 172 H290" />
          <rect x="138" y="18" width="24" height="20" />
        </svg>
      );
    case 'nacht':
      return (
        <>
          <span
            aria-hidden
            className="absolute inset-0"
            style={{
              backgroundImage:
                'radial-gradient(circle at 20% 15%, #fff 0 0.9px, transparent 1.3px), radial-gradient(circle at 55% 10%, #fff 0 0.8px, transparent 1.2px), radial-gradient(circle at 85% 40%, #fff 0 0.8px, transparent 1.2px), radial-gradient(circle at 12% 55%, #fff 0 0.8px, transparent 1.2px)',
            }}
          />
          <span
            aria-hidden
            className="absolute left-2 top-1.5 size-3.5 rounded-full"
            style={{ boxShadow: 'inset -4px -2px 0 0 #f1e9c8' }}
          />
        </>
      );
    case 'gold':
      return (
        <>
          {[
            'left-2.5 top-2.5',
            'right-2.5 top-2.5',
            'bottom-2.5 left-2.5',
            'bottom-2.5 right-2.5',
          ].map((position) => (
            <span
              key={position}
              aria-hidden
              className={cn('absolute size-[5px] rounded-full', position)}
              style={{ background: GOLD_ACCENT }}
            />
          ))}
        </>
      );
    case 'festlich':
      return (
        <span
          aria-hidden
          className="absolute inset-x-0 bottom-0 h-3 rounded-t-full bg-[#fbf5e6]"
        />
      );
    default:
      return null;
  }
}

type ThumbProps = {
  id: StyleId;
  daysPlayed: number;
  checked: boolean;
  isFresh: boolean;
  tabbable: boolean;
  onSelect: () => void;
  onKeyDown: (event: KeyboardEvent<HTMLButtonElement>) => void;
  buttonRef: (node: HTMLButtonElement | null) => void;
};

function Thumb({
  id,
  daysPlayed,
  checked,
  isFresh,
  tabbable,
  onSelect,
  onKeyDown,
  buttonRef,
}: ThumbProps) {
  const locked = isLocked(id, daysPlayed);
  const colours = thumbColours(id);

  return (
    <button
      ref={buttonRef}
      type="button"
      role="radio"
      aria-checked={checked}
      aria-disabled={locked}
      aria-label={thumbLabel(id, daysPlayed, isFresh)}
      tabIndex={tabbable ? 0 : -1}
      onClick={onSelect}
      onKeyDown={onKeyDown}
      className={cn(
        'flex min-w-0 flex-col gap-1.5 rounded-[10px] text-center text-[var(--daily-ink)]',
        locked && 'cursor-not-allowed',
        FOCUS_RING,
      )}
    >
      <span
        className={cn(
          'relative flex h-[104px] flex-col items-center gap-[5px] overflow-hidden rounded-[10px] px-1.5 py-2.5',
          locked && 'opacity-45',
        )}
        style={{
          background: colours.canvas,
          boxShadow: [
            id === 'gold' ? GOLD_RING : `inset 0 0 0 1px ${colours.border}`,
            checked
              ? '0 0 0 2px var(--daily-canvas), 0 0 0 4px var(--daily-ink)'
              : null,
          ]
            .filter(Boolean)
            .join(', '),
        }}
      >
        <ThumbDecor id={id} />
        <span
          aria-hidden
          className="relative h-[5px] w-[60%] rounded-[3px]"
          style={{ background: colours.ink }}
        />
        <b
          aria-hidden
          className={cn(
            'relative text-[18px] font-extrabold',
            id === 'papier' ? 'font-document' : 'font-display',
          )}
          style={{ color: colours.ink }}
        >
          4/5
        </b>
        <span
          aria-hidden
          className="relative h-[5px] w-[70%] rounded-[3px]"
          style={{ background: colours.muted }}
        />
      </span>
      {isFresh && !locked && (
        <span
          aria-hidden
          className="absolute right-1.5 top-1.5 rounded-full bg-brand-red px-1.5 py-px text-[11px] font-bold text-white"
        >
          Neu
        </span>
      )}
      {locked && (
        <span
          aria-hidden
          className="absolute right-1.5 top-1.5 inline-flex size-5 items-center justify-center rounded-full bg-black/55 text-white"
        >
          <Lock className="size-[11px]" strokeWidth={2.5} />
        </span>
      )}
      <span className="whitespace-nowrap text-xs font-semibold">
        {styleName(id)}
      </span>
      <span className="-mt-1 whitespace-nowrap text-[11px] text-[var(--daily-muted)]">
        {thumbSubline(id, daysPlayed)}
      </span>
    </button>
  );
}

/**
 * The bottom sheet for picking the result's style. The pick stays local until
 * the primary button, so browsing the thumbs never re-dresses the result.
 */
function StyleSheet({ open, onOpenChange }: Props) {
  const { style, fresh, daysPlayed } = useStimmtsStyle();
  const styles = visibleStyles(berlinMonth(new Date()));
  const [state, setState] = useState<SheetState>(() => openSheet(style, []));
  const { selected, freshOnOpen } = state;
  const thumbs = useRef<(HTMLButtonElement | null)[]>([]);
  const latest = useRef({ style, fresh });
  latest.current = { style, fresh };

  useEffect(() => {
    if (!open) {
      return;
    }
    const { style: current, fresh: unseen } = latest.current;
    const opened = openSheet(current, unseen);
    setState(opened);
    styleStore.getState().markSeen(opened.freshOnOpen);
  }, [open]);

  const select = (id: StyleId) => {
    setState((prev) => selectStyle(prev, id, !isLocked(id, daysPlayed)));
  };

  const handleKeyDown = (
    event: KeyboardEvent<HTMLButtonElement>,
    index: number,
  ) => {
    const target = nextIndex(index, event.key, styles.length, (i) => {
      const candidate = styles[i];
      return !candidate || isLocked(candidate, daysPlayed);
    });
    if (target === null) {
      return;
    }
    event.preventDefault();
    thumbs.current[target]?.focus();
    const id = styles[target];
    if (id) {
      select(id);
    }
  };

  const apply = () => {
    styleStore.getState().choose(confirmedStyle(state));
    onOpenChange(false);
  };

  // Tab lands on the checked thumb, the one the arrows start from. A locked
  // pick cannot be checked, so the group always has one.
  const tabStop = styles.includes(selected) ? selected : 'standard';

  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent className="daily-theme mx-auto max-w-md gap-[22px] rounded-t-2xl border-[var(--daily-border)] px-4 pb-7 pt-3 [&>div:first-child]:mt-0 [&>div:first-child]:h-1 [&>div:first-child]:min-h-0 [&>div:first-child]:w-10 [&>div:first-child]:self-center [&>div:first-child]:bg-[var(--daily-border)]">
        <div className="flex items-center justify-between">
          <DrawerTitle className="text-lg font-bold leading-normal tracking-normal">
            Stil ändern
          </DrawerTitle>
          <DrawerClose
            aria-label="Schließen"
            className={cn(
              'inline-flex size-11 items-center justify-center rounded-full',
              FOCUS_RING,
            )}
          >
            <X aria-hidden className="size-5" strokeWidth={2} />
          </DrawerClose>
        </div>
        <DrawerDescription className="sr-only">
          Wähle den Stil für dein Ergebnis und das Bild zum Teilen.
        </DrawerDescription>

        <div className="flex flex-col gap-2.5">
          <p className="text-[13px] text-[var(--daily-muted)]">
            <b className="text-[22px] font-extrabold text-[var(--daily-ink)]">
              {daysPlayed}
            </b>{' '}
            Tage gespielt
          </p>
          <ProgressBar daysPlayed={daysPlayed} />
        </div>

        <div
          role="radiogroup"
          aria-label="Stil für Ergebnis und Teilbild"
          className="grid gap-2 pb-2 pt-1"
          style={{
            gridTemplateColumns: `repeat(${gridColumns(styles.length)}, minmax(0, 1fr))`,
          }}
        >
          {styles.map((id, index) => (
            <div key={id} className="relative min-w-0">
              <Thumb
                id={id}
                daysPlayed={daysPlayed}
                checked={id === selected}
                isFresh={freshOnOpen.includes(id)}
                tabbable={id === tabStop}
                onSelect={() => select(id)}
                onKeyDown={(event) => handleKeyDown(event, index)}
                buttonRef={(node) => {
                  thumbs.current[index] = node;
                }}
              />
            </div>
          ))}
        </div>

        <button
          type="button"
          onClick={apply}
          className={cn(
            'h-11 rounded-full bg-[var(--daily-ink)] text-base font-semibold text-[var(--daily-canvas)] transition-opacity hover:opacity-90',
            FOCUS_RING,
          )}
        >
          {styleName(selected)} verwenden
        </button>
      </DrawerContent>
    </Drawer>
  );
}

function ProgressBar({ daysPlayed }: { daysPlayed: number }) {
  const fill = barFill(daysPlayed);
  return (
    <div
      role="img"
      aria-label={barLabel(daysPlayed)}
      className="relative mx-2 h-10"
    >
      <span className="absolute inset-x-0 top-0 h-1.5 rounded-full bg-[var(--daily-surface)]" />
      <span
        className="absolute left-0 top-0 h-1.5 rounded-full bg-[var(--daily-ink)]"
        style={{ width: `${fill}%` }}
      />
      {milestoneMarks(daysPlayed).map((mark) => (
        <span key={mark.days}>
          <span
            className={cn(
              'absolute -top-[5px] -ml-2 size-4 rounded-full border-2',
              mark.reached
                ? 'border-[var(--daily-ink)] bg-[var(--daily-ink)]'
                : 'border-[var(--daily-muted)] bg-[var(--daily-canvas)]',
            )}
            style={{ left: `${mark.at}%` }}
          />
          <span
            className={cn(
              'absolute top-[18px] -translate-x-1/2 text-xs font-bold',
              mark.reached
                ? 'text-[var(--daily-ink)]'
                : 'text-[var(--daily-muted)]',
            )}
            style={{ left: `${mark.at}%` }}
          >
            {mark.days}
          </span>
        </span>
      ))}
      <span
        className="absolute -top-[9px] -ml-[1.5px] h-6 w-[3px] rounded-sm bg-[var(--daily-ink)] shadow-[0_0_0_2px_var(--daily-canvas)]"
        style={{ left: `${fill}%` }}
      />
    </div>
  );
}

export default StyleSheet;

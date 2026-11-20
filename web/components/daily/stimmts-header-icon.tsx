'use client';

import { StimmtsMark } from '@/components/stimmts/stimmts-logo';
import { berlinDate } from '@/lib/stimmts/berlin-time';
import { nextFeedTick } from '@/lib/stimmts/feed-entry';
import { type TodaysResult, todaysResult } from '@/lib/stimmts/todays-result';
import { useProgress } from '@/lib/stimmts/use-progress';
import { useStimmtsStatus } from '@/lib/stimmts/use-stimmts-status';
import { cn } from '@/lib/utils';
import { useReducedMotion } from 'motion/react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { FOCUS_RING } from './card-styles';
import { ICON_LANDED_EVENT, ICON_TARGET_ATTRIBUTE } from './stimmts-fly-in';

const HINT_KEY = 'stimmts:icon-hint-shown';
const HINT_MS = 4000;
const HINT_FADE_MS = 300;

type Hint = 'shown' | 'fading' | null;

/** The hint is taught once per device; blocked storage means never. */
function claimHint(): boolean {
  try {
    if (window.localStorage.getItem(HINT_KEY)) {
      return false;
    }
    window.localStorage.setItem(HINT_KEY, '1');
    return true;
  } catch {
    return false;
  }
}

/** After the card has flown in: a pulse, and the hint the first time. */
function useLanding(reduceMotion: boolean): { pulse: boolean; hint: Hint } {
  const [pulse, setPulse] = useState(false);
  const [hint, setHint] = useState<Hint>(null);

  useEffect(() => {
    const onLanded = () => {
      setPulse(!reduceMotion);
      if (claimHint()) {
        setHint('shown');
      }
    };
    window.addEventListener(ICON_LANDED_EVENT, onLanded);
    return () => window.removeEventListener(ICON_LANDED_EVENT, onLanded);
  }, [reduceMotion]);

  useEffect(() => {
    if (hint === null) {
      return;
    }
    const timer = setTimeout(
      () => setHint(hint === 'shown' ? 'fading' : null),
      hint === 'shown' ? HINT_MS : HINT_FADE_MS,
    );
    return () => clearTimeout(timer);
  }, [hint]);

  return { pulse, hint };
}

/**
 * Today's result on this device, kept current: a tab left open past Berlin
 * midnight drops yesterday's score, and a game finished in another tab
 * counts on return. Null on the server and in the first browser render, so
 * both agree. It also moves the presence mark on, which the check's CSS
 * reads, on pages without the feed card to do it.
 */
function useTodaysResult(): TodaysResult | null {
  const hydrate = useProgress((s) => s.hydrate);
  const hydrated = useProgress((s) => s.hydrated);
  const refresh = useProgress((s) => s.refresh);
  const progress = useProgress((s) => s.progress);
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    hydrate();
    setNow(new Date());
    // A sleeping device delays timers, so coming back reads the clock again.
    const onVisible = () => {
      if (document.visibilityState === 'visible') {
        refresh();
        setNow(new Date());
      }
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, [hydrate, refresh]);

  useEffect(() => {
    if (!now) {
      return;
    }
    const timer = setTimeout(
      () => setNow(new Date()),
      nextFeedTick('played', now),
    );
    return () => clearTimeout(timer);
  }, [now]);

  const result =
    hydrated && now ? todaysResult(progress, berlinDate(now)) : null;
  const playedToday = result !== null;

  useEffect(() => {
    if (!hydrated || !now) {
      return;
    }
    const root = document.documentElement;
    if (playedToday) {
      root.dataset.stimmts = 'today';
    } else if (root.dataset.stimmts === 'today') {
      root.dataset.stimmts = 'before';
    }
  }, [hydrated, now, playedToday]);

  return result;
}

/**
 * The way back to Stimmt's? for someone who has played: the mark in the
 * header, with a check once today's game is done. It opens the game, which
 * shows today's result or the quiz menu.
 *
 * The header is shared and cached, so whether this device has ever played is
 * only known in the browser. The presence script marks <html> before first
 * paint and globals.css shows the icon (and its check) from that mark: no
 * flash, and no shift for the many readers who never played.
 *
 * Only while the switch is on: the server's reading decides the first paint,
 * so a switched-off game never shows its icon to past players, and the live
 * switch takes over once it answers. Loading or unreachable keeps the
 * server's decision. On any day of a running game, not only puzzle days: it
 * also leads to the result and the quiz menu after the last puzzle.
 *
 * Not on /stimmts itself, where it would only link to the page it is on.
 */
function StimmtsHeaderIcon({ serverEnabled }: { serverEnabled: boolean }) {
  const pathname = usePathname();
  const { state } = useStimmtsStatus();
  const reduceMotion = useReducedMotion() ?? false;
  const { pulse, hint } = useLanding(reduceMotion);
  const result = useTodaysResult();

  const enabled = state.kind === 'known' ? state.status.enabled : serverEnabled;
  if (pathname === '/stimmts' || !enabled) {
    return null;
  }
  const label = result
    ? `Stimmt’s? – heute ${result.correct} von ${result.total}. Ergebnis und Quiz`
    : 'Stimmt’s? – Ergebnis und Quiz';

  // The 44 px target reaches into the gaps beside it: the round 36 px face
  // is what shows, and the header has no width to spare on a phone.
  return (
    <span className="stimmts-header-icon relative -mx-1 flex-none">
      <Link
        href="/stimmts"
        prefetch={false}
        aria-label={label}
        {...{ [ICON_TARGET_ATTRIBUTE]: '' }}
        className={cn(
          FOCUS_RING,
          'flex size-11 items-center justify-center rounded-full',
        )}
      >
        <span className="relative flex size-9 items-center justify-center rounded-full bg-[var(--daily-surface)]">
          {pulse && <span aria-hidden className="stimmts-icon-pulse" />}
          <StimmtsMark className="h-3 w-[22px] flex-none" />
          <span
            aria-hidden
            className="stimmts-header-badge absolute right-[-3px] top-[-3px] size-4 items-center justify-center rounded-full border-2 border-[var(--daily-canvas)] bg-[var(--daily-yes)] text-[9px] font-extrabold leading-none text-[var(--daily-canvas)]"
          >
            ✓
          </span>
        </span>
      </Link>
      {/* Always in the page, so screen readers announce what is put in.
          Centred under the icon: the icon sits mid-header on a phone, where
          a tip aligned to either side would run off the screen. */}
      <span
        role="status"
        className={cn(
          'pointer-events-none absolute left-1/2 top-full z-40 flex -translate-x-1/2 flex-col items-center transition-opacity',
          hint === 'fading' ? 'opacity-0' : 'opacity-100',
        )}
        style={{ transitionDuration: `${HINT_FADE_MS}ms` }}
      >
        {hint && (
          <>
            <span
              aria-hidden
              className="size-0 border-x-[7px] border-b-[7px] border-x-transparent border-b-[var(--daily-ink)]"
            />
            <span className="whitespace-nowrap rounded-lg bg-[var(--daily-ink)] px-2.5 py-[7px] text-[13px] font-semibold text-[var(--daily-canvas)]">
              Hier findest du dein Ergebnis
            </span>
          </>
        )}
      </span>
    </span>
  );
}

export default StimmtsHeaderIcon;

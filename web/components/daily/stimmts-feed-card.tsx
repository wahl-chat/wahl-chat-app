'use client';

import StimmtsLogo from '@/components/stimmts/stimmts-logo';
import { rememberEntry } from '@/lib/stimmts/analytics';
import { berlinDate } from '@/lib/stimmts/berlin-time';
import { formatCountdown } from '@/lib/stimmts/countdown';
import {
  type FeedEntry,
  feedCardLabel,
  feedEntry,
  nextFeedTick,
} from '@/lib/stimmts/feed-entry';
import { browserSession, clearJustPlayed } from '@/lib/stimmts/presence';
import type { StimmtsStatus } from '@/lib/stimmts/status';
import { type TodaysResult, todaysResult } from '@/lib/stimmts/todays-result';
import { useProgress } from '@/lib/stimmts/use-progress';
import { useStimmtsStatus } from '@/lib/stimmts/use-stimmts-status';
import { cn } from '@/lib/utils';
import { ArrowRight, ChevronRight } from 'lucide-react';
import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { CARD_SURFACE, FOCUS_RING, MUTED_TEXT } from './card-styles';
import StimmtsFlyIn from './stimmts-fly-in';

// Set when the reader opens the card; from then on the shine is not needed.
const CARD_OPENED_KEY = 'stimmts:card-opened';

// Before mount the card shows no name or countdown, and below 360 px its
// button has no visible text; this keeps "Los geht’s" in the link's name.
const STATIC_LABEL = 'Stimmt’s?: Jeden Tag ein neues Quiz. Los geht’s';

type PlayEntry = Extract<FeedEntry, { kind: 'play' }>;

/**
 * The shine on "Los geht’s" keeps inviting, one gentle sweep every few
 * seconds, until the reader has opened the card once; after that it never
 * plays again. A reader who asked for less motion never sees it.
 */
function wantsShine(): boolean {
  try {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return false;
    }
    return !window.localStorage.getItem(CARD_OPENED_KEY);
  } catch {
    // Blocked storage could never remember the tap: better no shine than
    // one that never stops.
    return false;
  }
}

function rememberCardOpened() {
  rememberEntry('feed_card');
  try {
    window.localStorage.setItem(CARD_OPENED_KEY, '1');
  } catch {
    // Nothing to remember it in; the shine is already off for this reader.
  }
}

function useShine(active: boolean): boolean {
  const [shine, setShine] = useState(false);
  useEffect(() => {
    setShine(active && wantsShine());
  }, [active]);
  return shine;
}

/**
 * The invitation to today's Stimmt’s? above the Hot Topic: the whole card is
 * one link to the game.
 *
 * The feed page is shared by every reader, so the server only knows whether
 * a puzzle runs today (`initialStatus` is off when none does). It renders the
 * card with empty slots for the
 * puzzle's name and the countdown, at their final size, and the browser fills
 * them after mount: the feed below never moves. Whether this device has
 * played today is device state too; the presence script in the root layout
 * marks <html> before first paint and globals.css hides the card, so it never
 * flashes for someone who already played.
 */
function StimmtsFeedCard({ initialStatus }: { initialStatus: StimmtsStatus }) {
  const { state } = useStimmtsStatus();
  // Loading or unreachable: the server's answer stands, so a blocked
  // Firestore leaves the feed exactly as it was rendered.
  const status = state.kind === 'known' ? state.status : initialStatus;

  const hydrate = useProgress((s) => s.hydrate);
  const hydrated = useProgress((s) => s.hydrated);
  const refresh = useProgress((s) => s.refresh);
  const progress = useProgress((s) => s.progress);

  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    hydrate();
    setNow(new Date());
    // Playing in another tab and coming back retires the card. A sleeping
    // device delays timers, so coming back also reads the clock afresh.
    const onVisible = () => {
      if (document.visibilityState === 'visible') {
        refresh();
        setNow(new Date());
      }
    };
    document.addEventListener('visibilitychange', onVisible);
    window.addEventListener('focus', onVisible);
    return () => {
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener('focus', onVisible);
    };
  }, [hydrate, refresh]);

  const ready = now !== null && hydrated;

  const entry = ready ? feedEntry({ status, now, progress }) : null;
  const kind = entry?.kind;
  const shine = useShine(kind === 'play');

  // The countdown needs the clock every second.
  useEffect(() => {
    if (kind !== 'play') {
      return;
    }
    const timer = setInterval(
      () => setNow(new Date()),
      nextFeedTick(kind, new Date()),
    );
    return () => clearInterval(timer);
  }, [kind]);

  // Without a countdown, a tab left open still has to notice Berlin
  // midnight: a played day turns into a new puzzle, a launch day begins.
  // Each wake-up sets `now`, which schedules the next one.
  useEffect(() => {
    if (!status.enabled || kind === undefined || kind === 'play' || !now) {
      return;
    }
    const timer = setTimeout(() => setNow(new Date()), nextFeedTick(kind, now));
    return () => clearTimeout(timer);
  }, [status.enabled, kind, now]);

  // The presence mark is set once, before first paint. A tab left open past
  // Berlin midnight, or a game finished in another tab, has to move it on,
  // or the CSS rule keeps hiding a new day's card, or showing a played one.
  useEffect(() => {
    const root = document.documentElement;
    if (kind === 'play' && root.dataset.stimmts === 'today') {
      root.dataset.stimmts = 'before';
    } else if (kind === 'played') {
      root.dataset.stimmts = 'today';
    }
  }, [kind]);

  const flying = useFlyFlag(kind);
  const result =
    flying.active && kind === 'played' && now
      ? todaysResult(progress, berlinDate(now))
      : null;

  if (!status.enabled) {
    return null;
  }
  if (entry === null) {
    return <Card entry={null} now={null} shine={false} />;
  }
  if (result) {
    return (
      <StimmtsFlyIn onDone={flying.done}>
        <PlayedCard result={result} />
      </StimmtsFlyIn>
    );
  }
  // Played today and already flown in (or never to): the header icon holds
  // the result, as the presence rule said before first paint.
  if (entry.kind !== 'play' || now === null) {
    return null;
  }
  return <Card entry={entry} now={now} shine={shine} />;
}

/**
 * Whether this visit comes straight from finishing a game, which the game
 * marked on <html>. Read after mount, as the server cannot know. A flag that
 * does not fit the progress (a game reset since) is dropped, or the CSS
 * would keep the invitation hidden. A page restored from the back-forward
 * cache drops it too, so going back never replays the flight.
 */
function useFlyFlag(kind: FeedEntry['kind'] | undefined): {
  active: boolean;
  done: () => void;
} {
  const [active, setActive] = useState(false);
  const done = useCallback(() => setActive(false), []);

  useEffect(() => {
    setActive(document.documentElement.dataset.stimmtsFly !== undefined);
    const onShow = (event: PageTransitionEvent) => {
      if (event.persisted) {
        clearJustPlayed(browserSession(), document.documentElement);
        setActive(false);
      }
    };
    window.addEventListener('pageshow', onShow);
    return () => window.removeEventListener('pageshow', onShow);
  }, []);

  useEffect(() => {
    if (active && kind !== undefined && kind !== 'played') {
      clearJustPlayed(browserSession(), document.documentElement);
      setActive(false);
    }
  }, [active, kind]);

  return { active, done };
}

/**
 * Today's result, shown only on the way into the header icon: what the
 * player just finished, so they see it land where it now lives. It takes the
 * place of the hidden invitation the server rendered, so it keeps the
 * invitation's padding and row heights: the feed must not move before the
 * card leaves.
 */
function PlayedCard({ result }: { result: TodaysResult }) {
  return (
    <Link
      href="/stimmts"
      prefetch={false}
      data-variant="played"
      aria-label={`Stimmt’s? heute gespielt: ${result.correct} von ${result.total} richtig. Ergebnis ansehen`}
      className={cn(
        'stimmts-feed-card flex items-center gap-3 pb-3 pl-3.5 pr-2.5 pt-2.5 text-[var(--daily-ink)] no-underline',
        CARD_SURFACE,
        FOCUS_RING,
      )}
    >
      <span className="flex min-w-0 flex-1 flex-col gap-1.5">
        <span
          className={cn(
            'flex h-[18px] items-center gap-1.5 whitespace-nowrap text-[13px] leading-[18px]',
            MUTED_TEXT,
          )}
        >
          <StimmtsLogo className="flex-none gap-[5px] text-[15px] text-[var(--daily-ink)] [&>svg]:h-3" />
          <span>· Heute gespielt</span>
        </span>
        {/* The invitation's second row: room for a two-line name on a
            phone, the 40 px button from sm up. */}
        <span className="flex min-h-[59px] items-center gap-2 whitespace-nowrap sm:min-h-10">
          <span className="text-xl font-extrabold leading-6">
            {result.correct}/{result.total}
          </span>
          <span aria-hidden className="ml-1 inline-flex flex-none gap-0.5">
            {result.verdicts.map((right, index) => (
              <span
                // Seating order never changes within a result.
                // biome-ignore lint/suspicious/noArrayIndexKey: fixed order
                key={index}
                className={cn(
                  'inline-flex size-[13px] items-center justify-center rounded-full text-[8px] font-extrabold text-[var(--daily-canvas)]',
                  right ? 'bg-[var(--daily-yes)]' : 'bg-[var(--daily-no)]',
                )}
              >
                {right ? '✓' : '✗'}
              </span>
            ))}
          </span>
        </span>
      </span>
      <ChevronRight
        aria-hidden
        className={cn('size-5 flex-none', MUTED_TEXT)}
        strokeWidth={2}
      />
    </Link>
  );
}

function Card({
  entry,
  now,
  shine,
}: {
  entry: PlayEntry | null;
  now: Date | null;
  shine: boolean;
}) {
  const remaining =
    entry && now ? entry.endsAt.getTime() - now.getTime() : null;
  const label = entry && now ? feedCardLabel(entry, now) : null;

  return (
    <Link
      href="/stimmts"
      // A promotion on the busiest page: the game loads when it is chosen,
      // not for every reader who scrolls past.
      prefetch={false}
      onClick={rememberCardOpened}
      aria-label={label ?? STATIC_LABEL}
      className={cn(
        'stimmts-feed-card flex flex-col gap-1.5 px-3.5 pb-3 pt-2.5 text-[var(--daily-ink)] no-underline',
        CARD_SURFACE,
        FOCUS_RING,
      )}
    >
      <span
        className={cn(
          'flex h-[18px] min-w-0 items-center gap-1.5 whitespace-nowrap text-[13px] leading-[18px]',
          MUTED_TEXT,
        )}
      >
        {/* The design sets the mark 12 px high beside a 15 px wordmark;
            the logo's own height follows the font, which would make it 21. */}
        <StimmtsLogo className="flex-none gap-[5px] text-[15px] text-[var(--daily-ink)] [&>svg]:h-3" />
        {/* translate="no": a browser that auto-translates the page rewrites
            the text in place, which leaves the old time next to the new
            one. */}
        <span translate="no" className="ml-auto flex-none tabular-nums">
          {remaining === null ? null : formatCountdown(remaining)}
        </span>
      </span>
      {/* On a phone the name can take two lines, and whether it does is
          only known once it is filled in; the row keeps room for two from
          the start, so filling it never moves the feed. From sm up the
          longest name fits on one line. */}
      <span className="flex min-h-[59px] items-center gap-3 sm:min-h-0">
        <span className="flex min-w-0 flex-1 flex-col gap-px">
          <span className="line-clamp-2 min-h-5 text-[15px] font-bold leading-5">
            {entry ? `Heute: ${entry.shortName}` : null}
          </span>
          <span className={cn('text-[13px] leading-[18px]', MUTED_TEXT)}>
            Jeden Tag ein neues Quiz
          </span>
        </span>
        {/* Below 360 px the labelled button leaves the name too little room
            (the longest needs three lines), so it shrinks to its arrow. The
            link's own label still says "Los geht’s". */}
        <span
          className={cn(
            'inline-flex h-10 flex-none items-center justify-center gap-[5px] rounded-full bg-[var(--daily-ink)] px-3.5 text-sm font-semibold text-[var(--daily-canvas)] max-[359px]:w-10 max-[359px]:px-0',
            shine && 'stimmts-shine',
          )}
        >
          <span className="max-[359px]:hidden">Los geht’s</span>
          <ArrowRight aria-hidden className="size-4" strokeWidth={2.25} />
        </span>
      </span>
    </Link>
  );
}

export default StimmtsFeedCard;

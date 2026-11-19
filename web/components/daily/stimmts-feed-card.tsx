'use client';

import StimmtsLogo from '@/components/stimmts/stimmts-logo';
import { berlinDate } from '@/lib/stimmts/berlin-time';
import { formatCountdown } from '@/lib/stimmts/countdown';
import {
  type FeedEntry,
  feedCardLabel,
  feedEntry,
  recordFeedVisit,
  remainingLabel,
} from '@/lib/stimmts/feed-entry';
import { browserStorage } from '@/lib/stimmts/progress-store';
import type { StimmtsStatus } from '@/lib/stimmts/status';
import { useProgress } from '@/lib/stimmts/use-progress';
import { useStimmtsStatus } from '@/lib/stimmts/use-stimmts-status';
import { cn } from '@/lib/utils';
import { ArrowRight } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { CARD_SURFACE, FOCUS_RING, MUTED_TEXT } from './card-styles';

const SHINE_KEY = 'stimmts:shine-shown';

type PlayEntry = Extract<FeedEntry, { kind: 'play' }>;

/**
 * The shine on "Los geht’s" plays on the very first view only, so it draws
 * the eye once and never becomes noise. A reader who asked for less motion
 * never sees it, and does not use it up either.
 */
function claimShine(): boolean {
  try {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return false;
    }
    if (window.localStorage.getItem(SHINE_KEY)) {
      return false;
    }
    window.localStorage.setItem(SHINE_KEY, '1');
    return true;
  } catch {
    // Blocked storage could not keep the "once": better no shine than one
    // on every visit.
    return false;
  }
}

function useShine(active: boolean): boolean {
  const [shine, setShine] = useState(false);
  const [claimed, setClaimed] = useState(false);
  useEffect(() => {
    if (active && !claimed) {
      setClaimed(true);
      setShine(claimShine());
    }
  }, [active, claimed]);
  return shine;
}

/**
 * The invitation to today's Stimmt’s? above the Hot Topic: the whole card is
 * one link to the game.
 *
 * The feed page is cached and shared by every reader, so the server only
 * knows whether the game is on. It renders the card with empty slots for the
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
  const [visitDays, setVisitDays] = useState<number | null>(null);

  useEffect(() => {
    hydrate();
    setNow(new Date());
    // Playing in another tab and coming back retires the card.
    const onVisible = () => {
      if (document.visibilityState === 'visible') {
        refresh();
      }
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, [hydrate, refresh]);

  useEffect(() => {
    if (!status.enabled) {
      return;
    }
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, [status.enabled]);

  // Visits count only while the game is on, so a reader who came by before
  // the launch still sees the card as new once it starts.
  useEffect(() => {
    if (status.enabled && visitDays === null) {
      setVisitDays(recordFeedVisit(browserStorage(), berlinDate(new Date())));
    }
  }, [status.enabled, visitDays]);

  const ready = now !== null && hydrated && visitDays !== null;
  const entry = ready ? feedEntry({ status, now, progress, visitDays }) : null;
  const shine = useShine(entry?.kind === 'play');

  if (!status.enabled) {
    return null;
  }
  if (entry === null) {
    return <Card entry={null} now={null} shine={false} />;
  }
  // A game played today gets its own card later; until then nothing shows,
  // as the presence rule already did before first paint.
  if (entry.kind !== 'play' || now === null) {
    return null;
  }
  return <Card entry={entry} now={now} shine={shine} />;
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
      aria-label={label ?? undefined}
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
        {/* The board's mark is 12 px high beside a 15 px wordmark; the
            logo's own height follows the font, which would make it 21. */}
        <StimmtsLogo className="flex-none gap-[5px] text-[15px] text-[var(--daily-ink)] [&>svg]:h-3" />
        {entry?.isNew && (
          <span className="inline-flex h-[18px] flex-none items-center rounded-full border border-[var(--daily-ink)] px-[7px] text-[11px] font-bold text-[var(--daily-ink)]">
            Neu
          </span>
        )}
        {/* translate="no": a browser that auto-translates the page rewrites
            the text in place, which leaves the old time next to the new
            one. */}
        <span
          translate="no"
          aria-label={
            remaining === null ? undefined : `noch ${remainingLabel(remaining)}`
          }
          className="ml-auto flex-none tabular-nums"
        >
          {remaining === null ? null : `noch ${formatCountdown(remaining)}`}
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

'use client';

import { useStudyRunning } from '@/components/providers/study-status-provider';
import { type MoreGamesAnswer, trackMoreGames } from '@/lib/stimmts/analytics';
import {
  finishedGameCount,
  markAsked,
  shouldShowFeedCard,
  wasAsked,
} from '@/lib/stimmts/feedback';
import { browserStorage } from '@/lib/stimmts/progress-store';
import { useProgress } from '@/lib/stimmts/use-progress';
import { useStimmtsStatus } from '@/lib/stimmts/use-stimmts-status';
import { cn } from '@/lib/utils';
import { X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { CARD_SURFACE, FOCUS_RING } from './card-styles';

// The card waits a moment so it never competes with the feed's first paint.
const SLIDE_IN_DELAY_MS = 1200;
const THANKS_MS = 2500;

const ANSWER_BUTTON = cn(
  'min-h-11 flex-1 rounded-full border border-[var(--daily-border)] px-4 text-sm font-semibold text-[var(--daily-ink)] hover:bg-[var(--daily-border)]/40',
  FOCUS_RING,
);

/**
 * Asks once, on a feed visit after the first finished puzzle, whether we
 * should make more small games. It asks about the format only, never about a
 * vote, so it names no bill. An answer or a close both count as asked, so it
 * never returns. It never takes focus: it is a small aside at the bottom of a
 * page the reader came to read.
 */
function StimmtsFeedbackCard() {
  const studyRunning = useStudyRunning();
  const { state } = useStimmtsStatus();
  const gameOn = state.kind === 'known' ? state.status.enabled : null;
  const progress = useProgress((state) => state.progress);
  const hydrated = useProgress((state) => state.hydrated);
  const hydrate = useProgress((state) => state.hydrate);
  // Unknown until mounted, so it never flashes up for someone already asked
  // or on the visit the game's fly-in plays.
  const [mounted, setMounted] = useState<{
    asked: boolean;
    flyingIn: boolean;
  } | null>(null);
  const [visible, setVisible] = useState(false);
  const [answered, setAnswered] = useState(false);
  const [closed, setClosed] = useState(false);
  const closeButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    hydrate();
    setMounted({
      asked: wasAsked(browserStorage()),
      flyingIn: document.documentElement.dataset.stimmtsFly !== undefined,
    });
  }, [hydrate]);

  const eligible =
    hydrated &&
    mounted !== null &&
    shouldShowFeedCard({
      progress,
      asked: mounted.asked,
      studyRunning: studyRunning ?? null,
      flyingIn: mounted.flyingIn,
      gameOn,
    });
  const shown = !closed && (eligible || answered);

  useEffect(() => {
    if (!eligible) {
      return;
    }
    const timer = setTimeout(() => setVisible(true), SLIDE_IN_DELAY_MS);
    return () => clearTimeout(timer);
  }, [eligible]);

  const games = finishedGameCount(progress);

  const close = useCallback(() => {
    markAsked(browserStorage());
    setClosed(true);
    if (!answered) {
      trackMoreGames('dismissed', games, 'feed');
    }
  }, [answered, games]);

  useEffect(() => {
    if (!answered) {
      return;
    }
    // The answer buttons just unmounted, which would drop focus to the page.
    closeButton.current?.focus();
    const timer = setTimeout(() => setClosed(true), THANKS_MS);
    return () => clearTimeout(timer);
  }, [answered]);

  if (!shown || !visible) {
    return null;
  }

  const answer = (value: Exclude<MoreGamesAnswer, 'dismissed'>) => {
    markAsked(browserStorage());
    setAnswered(true);
    trackMoreGames(value, games, 'feed');
  };

  return (
    // Escape is handled here, not on window: it only counts when focus is in
    // the card, so closing another dialog never dismisses a question the
    // reader has not seen.
    <section
      aria-label="Kurze Frage zu Stimmt’s?"
      onKeyDown={(event) => {
        if (event.key === 'Escape') {
          close();
        }
      }}
      className={cn(
        'daily-theme fixed inset-x-4 bottom-4 z-40 mx-auto flex max-w-[400px] animate-stimmts-screen flex-col gap-3 p-4 shadow-lg motion-reduce:animate-none',
        CARD_SURFACE,
      )}
    >
      <div className="flex items-start justify-between gap-2">
        {answered ? (
          <p role="status" className="pt-2.5 font-semibold">
            Danke dir!
          </p>
        ) : (
          <p className="text-balance pt-2.5 text-[15px]">
            <strong className="font-semibold">Stimmt’s? ist neu.</strong> Sollen
            wir mehr kleine Spiele machen?
          </p>
        )}
        <button
          type="button"
          ref={closeButton}
          onClick={close}
          aria-label="Schließen"
          className={cn(
            'grid size-11 shrink-0 place-items-center rounded-md text-[var(--daily-muted)] hover:text-[var(--daily-ink)]',
            FOCUS_RING,
          )}
        >
          <X aria-hidden className="size-4" />
        </button>
      </div>
      {answered ? null : (
        <div className="flex gap-2">
          <button
            type="button"
            className={ANSWER_BUTTON}
            onClick={() => answer('yes')}
          >
            Ja, gern
          </button>
          <button
            type="button"
            className={ANSWER_BUTTON}
            onClick={() => answer('no')}
          >
            Eher nicht
          </button>
        </div>
      )}
    </section>
  );
}

export default StimmtsFeedbackCard;

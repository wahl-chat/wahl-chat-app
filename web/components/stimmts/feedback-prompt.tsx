import { useStudyRunning } from '@/components/providers/study-status-provider';
import { Button } from '@/components/ui/button';
import { type MoreGamesAnswer, trackMoreGames } from '@/lib/stimmts/analytics';
import {
  finishedGameCount,
  shouldAskForFeedback,
} from '@/lib/stimmts/feedback';
import { useProgress } from '@/lib/stimmts/use-progress';
import { cn } from '@/lib/utils';
import { X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { OUTLINE_BUTTON } from './pill-button';

// Not the key of the earlier star rating, so a player who was asked that is
// still asked this.
const ASKED_KEY = 'stimmts:more-games-asked';

// Without storage the flag below still keeps another day's result from asking
// again in the same visit; only a reload may ask once more.
let askedThisSession = false;

function wasAsked(): boolean {
  if (askedThisSession) {
    return true;
  }
  try {
    return window.localStorage.getItem(ASKED_KEY) === '1';
  } catch {
    return false;
  }
}

function markAsked() {
  askedThisSession = true;
  try {
    window.localStorage.setItem(ASKED_KEY, '1');
  } catch {
    // Nothing to remember it in beyond this visit.
  }
}

/**
 * Asks once, after the first finished puzzle, whether we should make more
 * small games. It asks about the format only, never about the vote or its
 * topic, so the card names no bill. An answer or a close both count as asked,
 * so the card never returns. While the PledgeTracker study runs, its
 * questionnaire is the only thing anyone is asked for, so the card stays away.
 */
function FeedbackPrompt() {
  const studyRunning = useStudyRunning();
  const progress = useProgress((state) => state.progress);
  // Unknown until mounted, so it never flashes up for someone already asked.
  const [asked, setAsked] = useState(true);
  const [answered, setAnswered] = useState(false);
  const [closed, setClosed] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => setAsked(wasAsked()), []);
  // The answer buttons unmount on an answer; without this, focus falls back
  // to the page and a keyboard user loses their place.
  useEffect(() => {
    if (answered) {
      closeRef.current?.focus();
    }
  }, [answered]);

  const games = finishedGameCount(progress);
  // Only a study status known to be off lets the card show: "not known yet"
  // could still turn out to be on. The game itself needs Firestore, so a
  // player who cannot reach it is not losing a question they could answer.
  const studyKnownOff = studyRunning === false;
  // An answer keeps the card (now a thank-you) until it is closed.
  if (
    !studyKnownOff ||
    closed ||
    (!answered && !shouldAskForFeedback(progress, asked))
  ) {
    return null;
  }

  const answer = (value: Exclude<MoreGamesAnswer, 'dismissed'>) => {
    markAsked();
    setAnswered(true);
    trackMoreGames(value, games);
  };
  const close = () => {
    markAsked();
    setClosed(true);
    if (!answered) {
      trackMoreGames('dismissed', games);
    }
  };

  return (
    <section
      aria-labelledby="stimmts-feedback"
      className="flex w-full flex-col items-center gap-3 rounded-lg border border-[var(--daily-border)] bg-[var(--daily-canvas)] p-4 text-center"
    >
      <div className="flex w-full items-start justify-between gap-3">
        <span aria-hidden className="size-8 shrink-0" />
        <h2 id="stimmts-feedback" className="text-balance pt-1 font-semibold">
          {answered
            ? 'Danke dir!'
            : 'Stimmt’s? ist neu. Sollen wir mehr kleine Spiele machen?'}
        </h2>
        <button
          ref={closeRef}
          type="button"
          onClick={close}
          aria-label="Schließen"
          className="grid size-8 shrink-0 place-items-center rounded-md text-[var(--daily-muted)] hover:text-[var(--daily-ink)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--daily-ink)]"
        >
          <X aria-hidden className="size-4" />
        </button>
      </div>
      {answered ? (
        <p role="status" className="text-sm text-[var(--daily-muted)]">
          Deine Antwort hilft uns, zu entscheiden, was wir als Nächstes bauen.
        </p>
      ) : (
        <div className="flex w-full max-w-xs gap-2">
          <Button
            size="lg"
            variant="outline"
            className={cn(OUTLINE_BUTTON, 'flex-1 px-4')}
            onClick={() => answer('yes')}
          >
            Ja, gern
          </Button>
          <Button
            size="lg"
            variant="outline"
            className={cn(OUTLINE_BUTTON, 'flex-1 px-4')}
            onClick={() => answer('no')}
          >
            Eher nicht
          </Button>
        </div>
      )}
    </section>
  );
}

export default FeedbackPrompt;

import { useStudyRunning } from '@/components/providers/study-status-provider';
import { Button } from '@/components/ui/button';
import { type MoreGamesAnswer, trackMoreGames } from '@/lib/stimmts/analytics';
import {
  finishedGameCount,
  shouldAskForFeedback,
} from '@/lib/stimmts/feedback';
import { useProgress } from '@/lib/stimmts/use-progress';
import { X } from 'lucide-react';
import { useEffect, useState } from 'react';

// Not the key of the earlier star rating, so a player who was asked that is
// still asked this.
const ASKED_KEY = 'stimmts:more-games-asked';

// Only a convenience: without storage a player may be asked once more.
function wasAsked(): boolean {
  try {
    return window.localStorage.getItem(ASKED_KEY) === '1';
  } catch {
    return false;
  }
}

function markAsked() {
  try {
    window.localStorage.setItem(ASKED_KEY, '1');
  } catch {
    // Nothing to remember it in.
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
  useEffect(() => setAsked(wasAsked()), []);

  const games = finishedGameCount(progress);
  // An answer keeps the card (now a thank-you) until it is closed.
  if (
    studyRunning ||
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
      className="flex w-full flex-col items-center gap-3 rounded-lg border bg-card p-4 text-center"
    >
      <div className="flex w-full items-start justify-between gap-3">
        <span aria-hidden className="size-4 shrink-0" />
        <h2 id="stimmts-feedback" className="text-balance font-semibold">
          {answered
            ? 'Danke dir!'
            : 'Stimmt’s? ist neu. Sollen wir mehr kleine Spiele machen?'}
        </h2>
        <button
          type="button"
          onClick={close}
          aria-label="Schließen"
          className="shrink-0 rounded-sm text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <X aria-hidden className="size-4" />
        </button>
      </div>
      {answered ? (
        <p role="status" className="text-sm text-muted-foreground">
          Deine Antwort hilft uns, zu entscheiden, was wir als Nächstes bauen.
        </p>
      ) : (
        <div className="flex w-full max-w-xs gap-2">
          <Button
            size="lg"
            variant="outline"
            className="flex-1 px-4"
            onClick={() => answer('yes')}
          >
            Ja, gern
          </Button>
          <Button
            size="lg"
            variant="outline"
            className="flex-1 px-4"
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

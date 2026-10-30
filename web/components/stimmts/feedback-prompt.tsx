import '@fillout/react/style.css';
import { Button } from '@/components/ui/button';
import { trackRated, trackRatingDismissed } from '@/lib/stimmts/analytics';
import {
  STIMMTS_FEEDBACK_FORM_ID,
  finishedGameCount,
  shouldAskForFeedback,
} from '@/lib/stimmts/feedback';
import { useProgress } from '@/lib/stimmts/use-progress';
import { cn } from '@/lib/utils';
import { FilloutPopupEmbed } from '@fillout/react';
import { Star, X } from 'lucide-react';
import { useEffect, useState } from 'react';

const ASKED_KEY = 'stimmts:feedback-asked';
const STARS = [1, 2, 3, 4, 5];

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
 * Asks once, after the fifth finished puzzle, how players like the game: a
 * single tap on a star, because a written form is mostly closed unread. Only
 * then is there an offer to say more. A rating or a close both count as
 * asked, so the card never returns.
 */
function FeedbackPrompt() {
  const progress = useProgress((state) => state.progress);
  // Unknown until mounted, so it never flashes up for someone already asked.
  const [asked, setAsked] = useState(true);
  const [rating, setRating] = useState<number | null>(null);
  const [hovered, setHovered] = useState<number | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [closed, setClosed] = useState(false);
  useEffect(() => setAsked(wasAsked()), []);

  const games = finishedGameCount(progress);
  // A rating keeps the card (now a thank-you) until it is closed.
  if (closed || (rating === null && !shouldAskForFeedback(progress, asked))) {
    return null;
  }

  const rate = (stars: number) => {
    markAsked();
    setRating(stars);
    trackRated(stars, games);
  };
  const close = () => {
    markAsked();
    setClosed(true);
    if (rating === null) {
      trackRatingDismissed(games);
    }
  };

  return (
    <section
      aria-labelledby="stimmts-feedback"
      className="flex w-full flex-col items-center gap-3 rounded-lg border bg-card p-4 text-center"
    >
      <div className="flex w-full items-start justify-between gap-3">
        <span aria-hidden className="size-4" />
        <h2 id="stimmts-feedback" className="font-semibold">
          {rating === null ? 'Wie gefällt dir Stimmt’s?' : 'Danke dir!'}
        </h2>
        <button
          type="button"
          onClick={close}
          aria-label={rating === null ? 'Nicht jetzt' : 'Schließen'}
          className="text-muted-foreground hover:text-foreground"
        >
          <X aria-hidden className="size-4" />
        </button>
      </div>
      {rating === null ? (
        <div
          role="group"
          aria-label="Bewertung"
          className="flex gap-1"
          onMouseLeave={() => setHovered(null)}
        >
          {STARS.map((stars) => (
            <button
              key={stars}
              type="button"
              onClick={() => rate(stars)}
              onMouseEnter={() => setHovered(stars)}
              onFocus={() => setHovered(stars)}
              onBlur={() => setHovered(null)}
              aria-label={stars === 1 ? '1 Stern' : `${stars} Sterne`}
              className="rounded-md p-1.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Star
                aria-hidden
                strokeWidth={1.75}
                className={cn(
                  'size-8 transition-colors',
                  hovered !== null && stars <= hovered
                    ? 'fill-foreground text-foreground'
                    : 'text-muted-foreground',
                )}
              />
            </button>
          ))}
        </div>
      ) : (
        <p role="status" className="text-sm text-muted-foreground">
          Deine Bewertung hilft uns, das Spiel besser zu machen.
        </p>
      )}
      {rating !== null && STIMMTS_FEEDBACK_FORM_ID !== '' && (
        <Button size="sm" variant="outline" onClick={() => setFormOpen(true)}>
          Magst du uns mehr erzählen?
        </Button>
      )}
      {formOpen && (
        <FilloutPopupEmbed
          filloutId={STIMMTS_FEEDBACK_FORM_ID}
          onClose={() => setFormOpen(false)}
          parameters={{ rating: String(rating), games: String(games) }}
        />
      )}
    </section>
  );
}

export default FeedbackPrompt;

import '@fillout/react/style.css';
import { Button } from '@/components/ui/button';
import {
  STIMMTS_FEEDBACK_FORM_ID,
  finishedGameCount,
  shouldAskForFeedback,
} from '@/lib/stimmts/feedback';
import { useProgress } from '@/lib/stimmts/use-progress';
import { FilloutPopupEmbed } from '@fillout/react';
import { MessageCircleHeart, X } from 'lucide-react';
import { useEffect, useState } from 'react';

const ASKED_KEY = 'stimmts:feedback-asked';

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
 * One request for feedback, once a player has finished five puzzles. Opening
 * the form or closing the card both count as asked, so it never returns.
 */
function FeedbackPrompt() {
  const progress = useProgress((state) => state.progress);
  // Unknown until mounted, so it never flashes up for someone already asked.
  const [asked, setAsked] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  useEffect(() => setAsked(wasAsked()), []);

  if (!shouldAskForFeedback(progress, asked) && !formOpen) {
    return null;
  }

  const dismiss = () => {
    markAsked();
    setAsked(true);
  };

  return (
    <section
      aria-labelledby="stimmts-feedback"
      className="flex w-full flex-col gap-3 rounded-lg border bg-card p-4"
    >
      <div className="flex items-start justify-between gap-3">
        <h2 id="stimmts-feedback" className="font-semibold">
          Wie gefällt dir Stimmt’s?
        </h2>
        <button
          type="button"
          onClick={dismiss}
          aria-label="Nicht jetzt"
          className="text-muted-foreground hover:text-foreground"
        >
          <X aria-hidden className="size-4" />
        </button>
      </div>
      <p className="text-sm text-muted-foreground">
        Du hast schon {finishedGameCount(progress)} Rätsel gelöst. Sag uns in
        zwei Minuten, was dir gefällt und was wir besser machen können.
      </p>
      <Button
        size="sm"
        onClick={() => {
          dismiss();
          setFormOpen(true);
        }}
      >
        <MessageCircleHeart aria-hidden />
        Feedback geben
      </Button>
      {formOpen && (
        <FilloutPopupEmbed
          filloutId={STIMMTS_FEEDBACK_FORM_ID}
          onClose={() => setFormOpen(false)}
          parameters={{ games: String(finishedGameCount(progress)) }}
        />
      )}
    </section>
  );
}

export default FeedbackPrompt;

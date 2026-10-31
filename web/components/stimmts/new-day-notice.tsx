import { getGame } from '@/lib/stimmts/progress';
import { useProgress } from '@/lib/stimmts/use-progress';
import { X } from 'lucide-react';
import { useEffect, useState } from 'react';

type Notice = {
  /** The player had started yesterday's puzzle without finishing it. */
  leftOpen: boolean;
};

/**
 * Explains the jump when midnight passes while the page is open and a new
 * puzzle takes the old one's place, possibly mid-game.
 */
function NewDayNotice({ puzzleId }: { puzzleId: string }) {
  const progress = useProgress((state) => state.progress);
  const [previousId, setPreviousId] = useState(puzzleId);
  const [notice, setNotice] = useState<Notice | null>(null);

  // Compared during render, so the notice arrives with the new puzzle
  // rather than one frame after it.
  if (puzzleId !== previousId) {
    const before = getGame(progress, previousId);
    setPreviousId(puzzleId);
    setNotice({
      leftOpen:
        before.finishedOn === null && Object.keys(before.guesses).length > 0,
    });
  }

  useEffect(() => {
    if (notice) {
      window.scrollTo({ top: 0 });
    }
  }, [notice]);

  if (!notice) {
    return null;
  }
  return (
    <div
      role="status"
      className="mt-6 flex items-start gap-3 rounded-lg border bg-card p-4 text-sm"
    >
      <p className="flex-1">
        <span className="font-semibold">Neuer Tag, neues Rätsel.</span>{' '}
        {notice.leftOpen
          ? 'Das Rätsel von gestern ist um Mitternacht abgelaufen, deine angefangenen Tipps zählen leider nicht.'
          : 'Das Rätsel von gestern ist um Mitternacht zu Ende gegangen.'}
      </p>
      <button
        type="button"
        onClick={() => setNotice(null)}
        aria-label="Hinweis schließen"
        className="text-muted-foreground hover:text-foreground"
      >
        <X aria-hidden className="size-4" />
      </button>
    </div>
  );
}

export default NewDayNotice;

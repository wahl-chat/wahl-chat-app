import { Button } from '@/components/ui/button';
import { ANSWER_LABELS, ANSWER_ORDER, partyLabel } from '@/lib/stimmts/labels';
import type { Guesses, Puzzle } from '@/lib/stimmts/types';
import { useProgress } from '@/lib/stimmts/use-progress';
import { useEffect, useState } from 'react';

// The answer buttons stay in the same place from one party to the next, so a
// quick double tap would answer two parties at once. They wait a moment after
// each new party appears.
const TAP_GUARD_MS = 350;

type Props = {
  puzzle: Puzzle;
  guesses: Guesses;
  today: string;
};

function GuessStep({ puzzle, guesses, today }: Props) {
  const answer = useProgress((state) => state.answer);
  const next = puzzle.parties.find(
    (party) => guesses[party.partyId] === undefined,
  );
  const nextId = next?.partyId;

  const [ready, setReady] = useState(false);
  useEffect(() => {
    setReady(false);
    const timer = setTimeout(() => setReady(true), TAP_GUARD_MS);
    return () => clearTimeout(timer);
  }, [nextId]);

  // No party left means the game is finished; the page then shows the reveal.
  if (!next) {
    return null;
  }
  const position = puzzle.parties.indexOf(next) + 1;

  return (
    <section className="flex flex-col gap-4">
      <details className="rounded-md border p-3 text-sm">
        <summary className="cursor-pointer font-medium">Worum geht es?</summary>
        <p className="mt-2 leading-relaxed">{puzzle.briefing}</p>
      </details>
      <p className="text-sm font-medium">{puzzle.yesMeans}</p>

      <div className="flex flex-col gap-1 rounded-lg border p-4">
        <p className="text-sm text-muted-foreground">
          Partei {position} von {puzzle.parties.length}
        </p>
        <h2 className="text-xl font-semibold">{partyLabel(next.partyId)}</h2>
        <p>Wie hat die Partei abgestimmt?</p>
        <div className="mt-3 grid gap-2">
          {ANSWER_ORDER.map((option) => (
            <Button
              key={option}
              variant="outline"
              size="lg"
              disabled={!ready}
              onClick={() => answer(puzzle, next.partyId, option, today)}
            >
              {ANSWER_LABELS[option]}
            </Button>
          ))}
        </div>
      </div>
    </section>
  );
}

export default GuessStep;

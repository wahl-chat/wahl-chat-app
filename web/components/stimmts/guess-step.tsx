import { Button } from '@/components/ui/button';
import { currentPartyIndex } from '@/lib/stimmts/game-view';
import { seatCount } from '@/lib/stimmts/hemicycle';
import {
  ANSWER_LABELS,
  ANSWER_ORDER,
  partyLabel,
  yesMeaning,
} from '@/lib/stimmts/labels';
import type { Guesses, Puzzle } from '@/lib/stimmts/types';
import { useProgress } from '@/lib/stimmts/use-progress';
import { cn } from '@/lib/utils';
import { useEffect, useState } from 'react';
import PartyTile from './party-tile';
import VoteDot from './vote-dot';

// The answer buttons stay in the same place from one party to the next, so a
// quick double tap would answer two parties at once. They wait a moment after
// each new party appears. They are only marked unavailable, not disabled: a
// disabled button drops the keyboard focus, sending it back to the page top.
const TAP_GUARD_MS = 350;

type Props = {
  puzzle: Puzzle;
  guesses: Guesses;
  today: string;
};

/**
 * The card for the party being asked. While answering, this card and the
 * chamber above it are all there is on screen; what "Ja" means rides along
 * at the bottom, since every answer depends on it.
 */
function GuessStep({ puzzle, guesses, today }: Props) {
  const answer = useProgress((state) => state.answer);
  const index = currentPartyIndex(puzzle, guesses);
  const next = index >= 0 ? puzzle.parties[index] : undefined;
  const nextId = next?.partyId;

  const [ready, setReady] = useState(false);
  useEffect(() => {
    setReady(false);
    const timer = setTimeout(() => setReady(true), TAP_GUARD_MS);
    return () => clearTimeout(timer);
  }, [nextId]);

  // Keys 1 to 3 answer on a keyboard; no hint is shown for them.
  useEffect(() => {
    if (!nextId || !ready) {
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (
        // A held key repeats, and would answer every party in turn.
        event.repeat ||
        event.metaKey ||
        event.ctrlKey ||
        event.altKey ||
        target?.closest('input, textarea, [contenteditable="true"]')
      ) {
        return;
      }
      const option = ANSWER_ORDER[Number(event.key) - 1];
      if (option) {
        answer(puzzle, nextId, option, today);
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [answer, nextId, puzzle, ready, today]);

  // No party left means the game is finished; the page then shows the reveal.
  if (!next) {
    return null;
  }

  return (
    <section className="flex flex-col gap-4 rounded-lg border bg-card p-4">
      <div aria-hidden className="flex gap-1">
        {puzzle.parties.map((party, i) => (
          <span
            key={party.partyId}
            className={cn(
              'h-1 flex-1 rounded-full',
              i < index
                ? 'bg-foreground'
                : i === index
                  ? 'bg-muted-foreground'
                  : 'bg-border',
            )}
          />
        ))}
      </div>
      <p aria-live="polite" className="sr-only">
        Partei {index + 1} von {puzzle.parties.length}:{' '}
        {partyLabel(next.partyId)}
      </p>
      <div className="flex items-center gap-3">
        <PartyTile partyId={next.partyId} />
        <div>
          <p className="text-sm text-muted-foreground">
            Partei {index + 1} von {puzzle.parties.length} · {seatCount(next)}{' '}
            Sitze
          </p>
          <h2 className="text-xl font-semibold">{partyLabel(next.partyId)}</h2>
        </div>
      </div>
      <p className="text-lg font-semibold">Wie hat die Partei abgestimmt?</p>
      <div className="grid gap-2">
        {ANSWER_ORDER.map((option) => (
          <Button
            key={option}
            variant="outline"
            size="lg"
            aria-disabled={!ready}
            onClick={() => {
              if (ready) {
                answer(puzzle, next.partyId, option, today);
              }
            }}
            className="justify-start px-4 text-base aria-disabled:cursor-default aria-disabled:opacity-50"
          >
            <VoteDot kind={option} />
            {ANSWER_LABELS[option]}
          </Button>
        ))}
      </div>
      <p className="flex items-baseline gap-2 text-[13px] leading-[18px] text-muted-foreground">
        <VoteDot kind="yes" className="size-2 -translate-y-px" />
        <span>Ja bedeutet: {yesMeaning(puzzle.yesMeans)}</span>
      </p>
    </section>
  );
}

export default GuessStep;

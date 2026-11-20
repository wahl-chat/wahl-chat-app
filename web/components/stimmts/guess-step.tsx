import { Button } from '@/components/ui/button';
import { currentPartyIndex } from '@/lib/stimmts/game-view';
import { seatCount } from '@/lib/stimmts/hemicycle';
import {
  ANSWER_LABELS,
  ANSWER_ORDER,
  partyLabel,
  yesMeaning,
} from '@/lib/stimmts/labels';
import type { Guesses, Puzzle, VoteAnswer } from '@/lib/stimmts/types';
import { useProgress } from '@/lib/stimmts/use-progress';
import { cn } from '@/lib/utils';
import { useCallback, useEffect, useRef, useState } from 'react';
import PartyTile from './party-tile';
import { OUTLINE_BUTTON } from './pill-button';
import TipRow from './tip-row';
import VoteDot from './vote-dot';

// The answer buttons stay in the same place from one party to the next, so a
// quick double tap would answer two parties at once. They wait a moment after
// each new party appears, an edited one included. They are only marked unavailable, not disabled: a
// disabled button drops the keyboard focus, sending it back to the page top.
const TAP_GUARD_MS = 350;

type Props = {
  puzzle: Puzzle;
  guesses: Guesses;
  today: string;
  /** A party already answered, asked again to change its tip. */
  editing?: string;
  /** A tap on an answered party in the row above the card. */
  onEdit: (partyId: string) => void;
  /** After every answer, so the page can end an edit. */
  onAnswered?: () => void;
};

/**
 * The card for the party being asked: the first one without a tip, or the
 * one being edited. While answering, this card and the chamber above it are
 * all there is on screen; what "Ja" means rides along at the bottom, since
 * every answer depends on it.
 */
function GuessStep({
  puzzle,
  guesses,
  today,
  editing,
  onEdit,
  onAnswered,
}: Props) {
  const saveAnswer = useProgress((state) => state.answer);
  const editIndex = editing
    ? puzzle.parties.findIndex((party) => party.partyId === editing)
    : -1;
  const index = editIndex >= 0 ? editIndex : currentPartyIndex(puzzle, guesses);
  const next = index >= 0 ? puzzle.parties[index] : undefined;
  const nextId = next?.partyId;
  const selected = editIndex >= 0 && nextId ? guesses[nextId] : undefined;

  const answer = useCallback(
    (partyId: string, option: VoteAnswer) => {
      saveAnswer(puzzle, partyId, option, today);
      onAnswered?.();
    },
    [saveAnswer, puzzle, today, onAnswered],
  );

  // An edit is started from the row above, whose button may then no longer
  // be one (or be elsewhere), so the focus moves to the party now asked.
  const partyHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (editing) {
      partyHeading.current?.focus({ preventScroll: true });
    }
  }, [editing]);

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
        answer(nextId, option);
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [answer, nextId, ready]);

  // No party left means every party has a tip; the page then shows the review.
  if (!next) {
    return null;
  }

  return (
    <section className="flex flex-col gap-4 rounded-lg border border-[var(--daily-border)] bg-[var(--daily-canvas)] p-4">
      <TipRow
        puzzle={puzzle}
        guesses={guesses}
        current={next.partyId}
        onEdit={onEdit}
      />
      <div aria-hidden className="flex gap-1">
        {puzzle.parties.map((party, i) => (
          <span
            key={party.partyId}
            className={cn(
              'h-1 flex-1 rounded-full',
              i === index
                ? 'bg-[var(--daily-muted)]'
                : guesses[party.partyId] !== undefined
                  ? 'bg-[var(--daily-ink)]'
                  : 'bg-[var(--daily-border)]',
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
          <p className="text-sm text-[var(--daily-muted)]">
            Partei {index + 1} von {puzzle.parties.length} · {seatCount(next)}{' '}
            Sitze
          </p>
          <h2
            ref={partyHeading}
            tabIndex={-1}
            className="text-xl font-semibold focus:outline-none"
          >
            {partyLabel(next.partyId)}
          </h2>
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
            // Only an edit has a tip to show; a fresh party has none chosen.
            aria-pressed={selected ? option === selected : undefined}
            onClick={() => {
              if (ready) {
                answer(next.partyId, option);
              }
            }}
            className={cn(
              OUTLINE_BUTTON,
              'justify-start px-4 text-base aria-disabled:cursor-default aria-disabled:opacity-50 aria-pressed:border-2 aria-pressed:border-[var(--daily-ink)] aria-pressed:bg-[var(--daily-surface)]',
            )}
          >
            <VoteDot kind={option} />
            {ANSWER_LABELS[option]}
          </Button>
        ))}
      </div>
      <p className="flex items-baseline gap-2 text-[13px] leading-[18px] text-[var(--daily-muted)]">
        <VoteDot kind="yes" className="size-2 -translate-y-px" />
        <span>Ja bedeutet: {yesMeaning(puzzle.yesMeans)}</span>
      </p>
    </section>
  );
}

export default GuessStep;

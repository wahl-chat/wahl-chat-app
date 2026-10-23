import { ANSWER_LABELS } from '@/lib/stimmts/labels';
import type { VoteAnswer } from '@/lib/stimmts/types';
import { cn } from '@/lib/utils';
import VoteDot from './vote-dot';

type VotePillProps = {
  /** Null while the real vote is still hidden. */
  vote: VoteAnswer | null;
  /** A tip carries a ring, a real vote a filled dot. */
  kind: 'tip' | 'vote';
};

/**
 * A vote as a small bordered label. Only the dot carries the vote colour, so
 * a vote never looks like a verdict.
 */
export function VotePill({ vote, kind }: VotePillProps) {
  const base =
    'inline-flex h-6 items-center gap-1.5 self-start whitespace-nowrap rounded-full border px-2 text-[13px] font-medium leading-4';
  if (!vote) {
    return (
      <span
        className={cn(
          base,
          'min-w-10 justify-center border-dashed text-muted-foreground',
        )}
      >
        ?
      </span>
    );
  }
  return (
    <span className={base}>
      <VoteDot kind={vote} ring={kind === 'tip'} />
      {ANSWER_LABELS[vote]}
    </span>
  );
}

type VerdictProps = {
  correct: boolean;
  /** Just the glyph, with the word for screen readers. */
  compact?: boolean;
};

/**
 * Right or wrong, as a filled pill in the result colours, never the seat
 * colours: a red "Nein" seat must not read as a mistake.
 */
export function Verdict({ correct, compact = false }: VerdictProps) {
  const word = correct ? 'Richtig' : 'Falsch';
  return (
    <span
      className={cn(
        'inline-flex flex-none items-center justify-center gap-1 whitespace-nowrap rounded-full text-[13px] font-bold leading-4 text-background',
        correct ? 'bg-result-correct' : 'bg-result-wrong',
        compact ? 'size-6' : 'h-7 px-2.5',
      )}
    >
      <span aria-hidden>{correct ? '✓' : '✗'}</span>
      {compact ? <span className="sr-only">{word}</span> : word}
    </span>
  );
}

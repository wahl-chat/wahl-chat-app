import { cn } from '@/lib/utils';

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

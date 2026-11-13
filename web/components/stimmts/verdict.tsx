import { cn } from '@/lib/utils';

/**
 * Right or wrong, as a filled glyph in the result colours, never the seat
 * colours: a red "Nein" seat must not read as a mistake.
 */
export function Verdict({ correct }: { correct: boolean }) {
  return (
    <span
      className={cn(
        'inline-flex size-6 flex-none items-center justify-center rounded-full text-[13px] font-bold leading-4 text-background',
        correct ? 'bg-result-correct' : 'bg-result-wrong',
      )}
    >
      <span aria-hidden>{correct ? '✓' : '✗'}</span>
      <span className="sr-only">{correct ? 'Richtig' : 'Falsch'}</span>
    </span>
  );
}

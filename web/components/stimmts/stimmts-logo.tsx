import { MARK_SEATS, MARK_VIEWBOX, type MarkTone } from '@/lib/stimmts/logo';
import { cn } from '@/lib/utils';

const TONE_CLASSES: Record<MarkTone, string> = {
  no: 'fill-seat-no',
  abstain: 'fill-seat-abstain',
  yes: 'fill-seat-yes',
};

/** Radius of one of the mark's seats, a little larger than a period seat. */
const MARK_DOT = 0.095;

/**
 * The Stimmt's? logo, inline: the 30-seat mark (Nein left, Enthaltung on
 * top, Ja right) beside the name. Drawn in code from the seat tokens, so it
 * stays sharp and follows the theme. The name takes the surrounding colour.
 */
function StimmtsLogo({ className }: { className?: string }) {
  return (
    <span
      role="img"
      aria-label="Stimmt’s?"
      className={cn('inline-flex items-center gap-1.5', className)}
    >
      <svg viewBox={MARK_VIEWBOX} aria-hidden className="h-[1.4em] w-auto">
        {MARK_SEATS.map((seat) => (
          <circle
            key={`${seat.x},${seat.y}`}
            cx={seat.x}
            cy={seat.y}
            r={MARK_DOT}
            className={TONE_CLASSES[seat.tone]}
          />
        ))}
      </svg>
      <span
        aria-hidden
        className="whitespace-nowrap font-display font-extrabold leading-none tracking-[-0.035em]"
      >
        Stimmt’s?
      </span>
    </span>
  );
}

export default StimmtsLogo;

import { countdownTarget, formatCountdown } from '@/lib/stimmts/countdown';
import { useEffect, useState } from 'react';

/**
 * Counts down to the next Berlin midnight, when the next puzzle opens: above
 * the urn once today's card is in, and on the eve of the launch.
 */
function Countdown({ label = 'Nächstes Rätsel in' }: { label?: string }) {
  const [remaining, setRemaining] = useState(
    () => countdownTarget(new Date(), null) - Date.now(),
  );

  useEffect(() => {
    let target: number | null = null;
    const timer = setInterval(() => {
      target = countdownTarget(new Date(), target);
      setRemaining(target - Date.now());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <p className="flex animate-stimmts-screen flex-col items-center motion-reduce:animate-none">
      <span className="text-sm font-medium text-muted-foreground">{label}</span>
      {/* translate="no": a browser that auto-translates the page rewrites the
          text in place, which leaves the old time next to the new one. The
          size follows the screen, so the clock spans the column on a phone. */}
      <span
        role="timer"
        translate="no"
        className="font-display text-[min(21vw,7rem)] font-extrabold tabular-nums leading-none tracking-[-0.03em]"
      >
        {formatCountdown(remaining)}
      </span>
    </p>
  );
}

export default Countdown;

import { countdownTarget, formatCountdown } from '@/lib/stimmts/countdown';
import { useEffect, useState } from 'react';

/**
 * Counts down to the next Berlin midnight, when tomorrow's puzzle opens. It
 * sits large above the urn, once today's card is in.
 */
function Countdown() {
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
      <span className="text-xs font-medium text-muted-foreground">
        Nächstes Rätsel in
      </span>
      {/* translate="no": a browser that auto-translates the page rewrites the
          text in place, which leaves the old time next to the new one. */}
      <span
        role="timer"
        translate="no"
        className="font-display text-[44px] font-extrabold tabular-nums leading-[48px] tracking-[-0.02em]"
      >
        {formatCountdown(remaining)}
      </span>
    </p>
  );
}

export default Countdown;

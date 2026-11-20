import { countdownTarget, formatCountdown } from '@/lib/stimmts/countdown';
import { cn } from '@/lib/utils';
import { useEffect, useState } from 'react';

type Props = {
  label?: string;
  /**
   * Large when the countdown is the whole screen (the eve of the launch);
   * compact at the head of the result, where the score is the news.
   */
  size?: 'large' | 'compact';
};

/**
 * Counts down to the next Berlin midnight, when the next puzzle opens: at the
 * head of the result, and on the eve of the launch.
 */
function Countdown({ label = 'Nächstes Quiz in', size = 'large' }: Props) {
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

  const compact = size === 'compact';
  return (
    <p className="flex animate-stimmts-screen flex-col items-center motion-reduce:animate-none">
      <span
        className={cn(
          'font-medium text-[var(--daily-muted)]',
          compact ? 'text-[13px]' : 'text-sm',
        )}
      >
        {label}
      </span>
      {/* translate="no": a browser that auto-translates the page rewrites the
          text in place, which leaves the old time next to the new one. The
          large size follows the screen, so the clock spans a phone's column. */}
      <span
        role="timer"
        translate="no"
        className={cn(
          'font-display font-extrabold tabular-nums leading-none tracking-[-0.03em]',
          compact ? 'text-[min(64px,17vw)]' : 'text-[min(21vw,7rem)]',
        )}
      >
        {formatCountdown(remaining)}
      </span>
    </p>
  );
}

export default Countdown;

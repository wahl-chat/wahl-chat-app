import type { DigestVote } from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { CheckIcon, XIcon } from 'lucide-react';

// On its own, apart from the vote card, so Stimmt's? can show the badge
// without loading the card's footer and the Firebase client behind it.
export function OutcomeBadge({
  outcome,
  className,
}: {
  outcome: DigestVote['outcome'];
  className?: string;
}) {
  if (!outcome) {
    return null;
  }
  const passed = outcome === 'angenommen';
  const Icon = passed ? CheckIcon : XIcon;
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center gap-1 rounded-full px-3 py-1 text-sm font-semibold',
        passed
          ? 'bg-[var(--daily-yes-bg)] text-[var(--daily-yes)]'
          : 'bg-[var(--daily-no-bg)] text-[var(--daily-no)]',
        className,
      )}
    >
      <Icon className="size-3.5" strokeWidth={3} aria-hidden />
      {passed ? 'Angenommen' : 'Abgelehnt'}
    </span>
  );
}

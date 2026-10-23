import { cn } from '@/lib/utils';

export type DotKind = 'yes' | 'no' | 'abstain' | 'absent' | 'unaffiliated';

// Spelled out in full so Tailwind finds the classes.
const FILLED: Record<DotKind, string> = {
  yes: 'bg-seat-yes',
  no: 'bg-seat-no',
  abstain: 'bg-seat-abstain',
  absent: 'shadow-[inset_0_0_0_1.5px_rgb(var(--seat-absent-ring))]',
  unaffiliated: 'bg-seat-unaffiliated',
};

const RING: Record<DotKind, string> = {
  yes: 'shadow-[inset_0_0_0_2px_rgb(var(--seat-yes))]',
  no: 'shadow-[inset_0_0_0_2px_rgb(var(--seat-no))]',
  abstain: 'shadow-[inset_0_0_0_2px_rgb(var(--seat-abstain))]',
  absent: 'shadow-[inset_0_0_0_1.5px_rgb(var(--seat-absent-ring))]',
  unaffiliated: 'shadow-[inset_0_0_0_2px_rgb(var(--seat-unaffiliated))]',
};

type Props = {
  kind: DotKind;
  /** A ring is a tip; a filled dot is a real vote. */
  ring?: boolean;
  className?: string;
};

/** The vote key: always next to its word or in a legend, never alone. */
function VoteDot({ kind, ring = false, className }: Props) {
  return (
    <span
      aria-hidden
      className={cn(
        'inline-block size-2.5 flex-none rounded-full',
        ring ? RING[kind] : FILLED[kind],
        className,
      )}
    />
  );
}

export default VoteDot;

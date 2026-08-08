import { cn } from '@/lib/utils';
import { MousePointerClickIcon } from 'lucide-react';
import Link from 'next/link';

/**
 * Soft, drifting colour field standing in for the party logos on the landing
 * page, and the page's primary call to action: it links into the election shown
 * in the selector above it.
 *
 * The tints are deliberately faint. They should read as "there are parties
 * behind this" without being identifiable as any particular party's branding —
 * on a tool about elections, a recognisable party colour in the decoration
 * would look like a preference.
 */

type Blob = {
  color: string;
  /** Inset position, in %. */
  top: number;
  left: number;
  size: number;
  /** Seconds. Chosen not to share a common period, so the loop is not visible. */
  duration: number;
};

const BLOBS: Blob[] = [
  { color: '237 56 51', top: -10, left: 4, size: 46, duration: 18 },
  { color: '59 92 178', top: 24, left: 58, size: 52, duration: 23 },
  { color: '32 34 40', top: 46, left: 18, size: 44, duration: 29 },
  { color: '46 138 88', top: -4, left: 66, size: 38, duration: 34 },
  { color: '116 74 158', top: 40, left: 76, size: 42, duration: 41 },
];

type Props = {
  /** Election to open when the card is clicked. */
  href: string;
  /** Named in the accessible label, so the destination is not just "hier". */
  electionName: string;
  className?: string;
};

function ElectionBlurCard({ href, electionName, className }: Props) {
  return (
    <Link
      href={href}
      aria-label={`Chat zur ${electionName} starten`}
      className={cn(
        'group relative flex h-40 w-full items-center justify-center overflow-hidden rounded-md md:h-48',
        'border border-muted-foreground/20 transition-colors hover:border-muted-foreground/40',
        'bg-gradient-to-br from-zinc-100 via-zinc-200 to-zinc-100',
        'dark:from-zinc-800 dark:via-zinc-700 dark:to-zinc-800',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        className,
      )}
    >
      {BLOBS.map((blob) => (
        <span
          key={blob.color}
          aria-hidden="true"
          className="animate-blur-drift absolute rounded-full opacity-[0.10] blur-3xl dark:opacity-[0.16]"
          style={
            {
              top: `${blob.top}%`,
              left: `${blob.left}%`,
              width: `${blob.size}%`,
              aspectRatio: '1',
              backgroundColor: `rgb(${blob.color})`,
              '--blur-duration': `${blob.duration}s`,
            } as React.CSSProperties
          }
        />
      ))}

      {/* Silver sheen over the colour, so the card reads as metallic grey with
          hints of colour rather than as a rainbow. */}
      <span
        aria-hidden="true"
        className="absolute inset-0 bg-gradient-to-tr from-white/50 via-transparent to-white/30 dark:from-white/5 dark:to-white/10"
      />

      <span className="relative flex items-center gap-2 text-base font-semibold text-foreground">
        <MousePointerClickIcon
          className="size-7 shrink-0 transition-transform group-hover:scale-110"
          aria-hidden="true"
        />
        Klick hier um zu starten
      </span>
    </Link>
  );
}

export default ElectionBlurCard;

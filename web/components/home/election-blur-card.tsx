import { cn } from '@/lib/utils';

/**
 * Soft, drifting colour field shown on the landing page where a context page
 * shows its party logos.
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
  className?: string;
};

function ElectionBlurCard({ className }: Props) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        'relative h-40 w-full overflow-hidden rounded-md border border-muted-foreground/20 md:h-48',
        'bg-gradient-to-br from-zinc-100 via-zinc-200 to-zinc-100',
        'dark:from-zinc-800 dark:via-zinc-700 dark:to-zinc-800',
        className,
      )}
    >
      {BLOBS.map((blob) => (
        <span
          key={blob.color}
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
      <span className="absolute inset-0 bg-gradient-to-tr from-white/50 via-transparent to-white/30 dark:from-white/5 dark:to-white/10" />
    </div>
  );
}

export default ElectionBlurCard;

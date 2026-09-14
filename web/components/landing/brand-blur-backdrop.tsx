import { cn } from '@/lib/utils';

/**
 * Slowly drifting colour field behind the landing page hero.
 *
 * Purely decorative and never interactive — the hero states its own call to
 * action, and a clickable background competes with it. The palette is the
 * wahl.chat brand rather than anything party-coded: the logo's red over the
 * page ground, plus neutral blobs that flip from near-black to white so the
 * field carries the same weight in either theme.
 */

/** The red of the checkmark in the logo. */
const BRAND_RED = '237 56 51';
const NEAR_BLACK = '24 24 27';
const WHITE = '255 255 255';

type Blob = {
  id: string;
  /** rgb channel triples, per theme. */
  light: string;
  dark: string;
  /** Inset position and diameter, in % of the hero. */
  top: number;
  left: number;
  size: number;
  /** Seconds. Chosen not to share a common period, so the loop is not visible. */
  duration: number;
};

const BLOBS: Blob[] = [
  {
    id: 'red-left',
    light: BRAND_RED,
    dark: BRAND_RED,
    top: -14,
    left: 2,
    size: 48,
    duration: 18,
  },
  {
    id: 'ink-centre',
    light: NEAR_BLACK,
    dark: WHITE,
    top: 20,
    left: 32,
    size: 54,
    duration: 23,
  },
  {
    id: 'red-right',
    light: BRAND_RED,
    dark: BRAND_RED,
    top: 36,
    left: 66,
    size: 44,
    duration: 29,
  },
  {
    id: 'ink-bottom',
    light: NEAR_BLACK,
    dark: WHITE,
    top: 54,
    left: 8,
    size: 42,
    duration: 34,
  },
  {
    id: 'red-top',
    light: BRAND_RED,
    dark: BRAND_RED,
    top: -8,
    left: 62,
    size: 34,
    duration: 41,
  },
];

type Props = {
  className?: string;
};

function BrandBlurBackdrop({ className }: Props) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        'absolute inset-0 overflow-hidden bg-background',
        className,
      )}
    >
      {BLOBS.map((blob) => (
        <span
          key={blob.id}
          className="animate-blur-drift absolute rounded-full bg-[rgb(var(--blob))] opacity-[0.17] blur-3xl dark:bg-[rgb(var(--blob-dark))] dark:opacity-[0.28]"
          style={
            {
              top: `${blob.top}%`,
              left: `${blob.left}%`,
              width: `${blob.size}%`,
              aspectRatio: '1',
              '--blob': blob.light,
              '--blob-dark': blob.dark,
              '--blur-duration': `${blob.duration}s`,
            } as React.CSSProperties
          }
        />
      ))}

      {/* Washes the field back towards the page ground, so hero text keeps its
          contrast wherever the blobs happen to have drifted. */}
      <span className="absolute inset-0 bg-gradient-to-b from-background/30 via-transparent to-background/70" />
    </div>
  );
}

export default BrandBlurBackdrop;

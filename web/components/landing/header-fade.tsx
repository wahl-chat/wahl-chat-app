import {
  PINNED_HEIGHT,
  PINNED_INSET,
  PINNED_TOP,
} from '@/components/landing/pinned-layout';

/**
 * A light veil under the pinned mark.
 *
 * The C is only a glyph, so headlines would otherwise read straight through
 * it. The header stays mostly see-through; a short, faint wash around the
 * mark is what takes the hard edge off that cut.
 */

const CHROME_HEIGHT = PINNED_TOP + PINNED_HEIGHT;
const FADE = 24;
const HEIGHT = CHROME_HEIGHT + FADE;
/** Centre of the parked C: gutter plus half the glyph's ~40px width. */
const MARK_X = PINNED_INSET + 20;
const MARK_Y = PINNED_TOP + PINNED_HEIGHT / 2;

function HeaderFade() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-x-0 top-0 z-40"
      style={{
        height: HEIGHT,
        backgroundImage: [
          `radial-gradient(ellipse 88px 44px at ${MARK_X}px ${MARK_Y}px, hsl(var(--background) / 0.4) 0%, hsl(var(--background) / 0.12) 55%, transparent 75%)`,
          `linear-gradient(to bottom, hsl(var(--background) / 0.1) 0, transparent ${HEIGHT}px)`,
        ].join(', '),
      }}
    />
  );
}

export default HeaderFade;

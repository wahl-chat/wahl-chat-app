'use client';

import Logo from '@/components/chat/logo';
import {
  PINNED_HEIGHT,
  PINNED_INSET,
  PINNED_TOP,
} from '@/components/landing/pinned-layout';
import {
  clampProgress,
  lerp,
  useScrollMorph,
} from '@/lib/hooks/use-scroll-morph';
import { m, useTransform } from 'motion/react';

/**
 * The wordmark in the hero, which reduces to its C-and-tick glyph and pins
 * that to the top left as it scrolls away.
 *
 * Two phases. First the whole wordmark slides left until the C reaches the
 * gutter, so "WAHL." leaves past the edge of the page rather than dissolving
 * in place. Only then does the tail retract from the right, until the C is all
 * that is left.
 *
 * It clips the one large logo rather than cross-fading it into the standalone
 * icon: a cross-fade cannot make the mark *retract*, and it would put two
 * copies of it in the DOM. The glyph's position inside the artwork was
 * measured from the SVG (x 449.4–562.6 of an 880-wide viewBox), so the clip
 * lands exactly on it — the constants below are that measurement, not taste.
 *
 * See useScrollMorph for why this tracks the scroll rather than flipping at a
 * threshold.
 */

/** The C-and-tick glyph inside the large wordmark, as fractions of its width. */
const GLYPH_LEFT_FRACTION = 449.4 / 880;
const GLYPH_RIGHT_FRACTION = 562.6 / 880;
/** The glyph is very slightly shorter than the artwork it sits in. */
const GLYPH_HEIGHT_FRACTION = 113.3 / 114;

/** The wordmark starts only ~44px above its pinned position, so the morph is
 *  paced by scroll distance rather than by the gap to the edge. */
const MORPH_DISTANCE = 180;

/** Where the slide ends and the retract begins. */
const SLIDE_ENDS_AT = 0.55;

function HeroLogo() {
  const { placeholderRef, boxRef, isReady, progress } = useScrollMorph({
    pinnedTop: PINNED_TOP,
    morphDistance: MORPH_DISTANCE,
  });

  // Every value derives from the one progress track, as plain functions rather
  // than chained motion values: a transform with several sources did not
  // re-evaluate reliably when only one of them changed, which left the mark
  // stuck at the top after scrolling back up.
  const slide = (p: number) => clampProgress(p / SLIDE_ENDS_AT);
  const retract = (p: number) =>
    clampProgress((p - SLIDE_ENDS_AT) / (1 - SLIDE_ENDS_AT));

  /** Scaled so the glyph itself ends at the shared pinned height. */
  const glyphScale = (p: number) => {
    const height = boxRef.current?.height ?? 0;
    return height === 0
      ? 1
      : lerp(1, PINNED_HEIGHT / (height * GLYPH_HEIGHT_FRACTION), slide(p));
  };

  /** Viewport x of the artwork's left edge — usually off-screen while sliding. */
  const elementLeft = (p: number) => {
    const box = boxRef.current;
    if (!box) return 0;

    const glyphAtRest = box.left + GLYPH_LEFT_FRACTION * box.width;
    const glyphTarget = lerp(glyphAtRest, PINNED_INSET, slide(p));
    return glyphTarget - glyphScale(p) * GLYPH_LEFT_FRACTION * box.width;
  };

  const clipPath = useTransform(progress, (p) => {
    const box = boxRef.current;
    const scaledWidth = (box?.width ?? 0) * glyphScale(p);

    // The left edge tracks the page gutter, so the wordmark slides out past it
    // instead of being cut at an arbitrary point. It lands exactly on the
    // glyph once the slide is done.
    const left =
      scaledWidth === 0
        ? 0
        : clampProgress((PINNED_INSET - elementLeft(p)) / scaledWidth) * 100;
    const right = lerp(0, (1 - GLYPH_RIGHT_FRACTION) * 100, retract(p));

    return `inset(0 ${right}% 0 ${left}%)`;
  });

  const scale = useTransform(progress, glyphScale);
  const left = useTransform(progress, elementLeft);

  // Driven by the morph rather than the raw scroll: the wordmark sits only
  // ~44px above its pinned position, so tracking the scroll would slam it
  // against the top long before it had finished sliding.
  const top = useTransform(progress, (p) =>
    lerp(boxRef.current?.top ?? PINNED_TOP, PINNED_TOP, slide(p)),
  );

  const logo = <Logo variant="large" className="h-8 w-auto md:h-10" />;

  return (
    <div
      ref={placeholderRef}
      className="shrink-0 self-start"
      style={
        isReady
          ? {
              height: boxRef.current?.height,
              width: boxRef.current?.width,
            }
          : undefined
      }
    >
      {isReady ? (
        <m.div
          className="fixed z-50 origin-top-left"
          style={{ top, left, scale, clipPath }}
        >
          {logo}
        </m.div>
      ) : (
        logo
      )}
    </div>
  );
}

export default HeroLogo;

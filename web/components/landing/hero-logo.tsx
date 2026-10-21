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
import { m, useMotionValue } from 'motion/react';

/**
 * The wordmark in the hero, which reduces to its C-and-tick glyph.
 *
 * It is `fixed` at the header from the first paint: sitting in the document
 * flow and then flipping to a pinned top made the mark overshoot and snap
 * back up a frame later. Horizontal travel is still driven from scroll.
 *
 * Two phases, all at the wordmark's own size. First the C slides to the
 * gutter and pushes "WAHL." off the left edge of the page — the mask's left
 * cut tracks that gutter, so those letters leave past the edge rather than
 * dissolving through the middle of the headline. Then the tail to the right
 * of the C retracts, until the mark is all that is left.
 *
 * A zero-flow sizer (not the visible mark) is what useScrollMorph measures,
 * so width/left stay honest across the md breakpoint without a hole where
 * the wordmark used to sit.
 *
 * It masks the one large logo rather than cross-fading it into the standalone
 * icon: a cross-fade cannot make the mark *retract*, and it would put two
 * copies of it in the DOM. The glyph's position inside the artwork was
 * measured from the SVG (x 449.4–562.6 of an 880-wide viewBox), so the mask
 * lands exactly on it — the constants below are that measurement, not taste.
 *
 * A gradient mask rather than clip-path or a scrim: both cuts run through
 * letterforms, and slicing a glyph down its middle reads as a rendering fault.
 * A scrim would have to match whatever is behind it, and behind this sit the
 * drifting blur blobs and the screenshot wheel — nothing a flat overlay can
 * match. Masking the mark itself is independent of all of that.
 *
 * See useScrollMorph for why this tracks the scroll rather than flipping at a
 * threshold, and why the values are written in onUpdate rather than derived.
 */

/** The C-and-tick glyph inside the large wordmark, as fractions of its width. */
const GLYPH_LEFT_FRACTION = 449.4 / 880;
const GLYPH_RIGHT_FRACTION = 562.6 / 880;

/** Paced by scroll distance rather than by a gap to the edge — the mark is
 *  already at the pin line. Kept short so the collapse finishes before the
 *  headline has scrolled into the top band. */
const MORPH_DISTANCE = 80;

/** Where the C has finished pushing "WAHL." off the gutter. */
const LEFT_ENDS_AT = 0.55;

/** How far a moving edge dissolves over, as a % of the artwork's width. */
const EDGE_FADE = 7;

const percent = (value: number) => `${value.toFixed(2)}%`;

/** No fade and nothing hidden — the state before the first measurement. */
const FULLY_OPAQUE_MASK = 'linear-gradient(to right, #000 0%, #000 100%)';

function HeroLogo() {
  const left = useMotionValue(PINNED_INSET);
  const maskImage = useMotionValue(FULLY_OPAQUE_MASK);
  // A fixed element resolves percentages against the viewport, so the
  // artwork's own box has to be carried over explicitly — and re-set on every
  // update, which is what keeps it right across the md breakpoint.
  const width = useMotionValue(0);
  const height = useMotionValue(0);

  const { placeholderRef, isReady } = useScrollMorph({
    pinnedTop: PINNED_TOP,
    morphDistance: MORPH_DISTANCE,
    onUpdate: ({ progress, box }) => {
      const slide = clampProgress(progress / LEFT_ENDS_AT);
      const retractRight = clampProgress(
        (progress - LEFT_ENDS_AT) / (1 - LEFT_ENDS_AT),
      );

      // Positioned by where the *glyph* should land, so the C pushes
      // "WAHL." off the gutter rather than the artwork's left edge travelling.
      const glyphAtRest = box.left + GLYPH_LEFT_FRACTION * box.width;
      const glyphTarget = lerp(glyphAtRest, PINNED_INSET, slide);
      const elementLeft = glyphTarget - GLYPH_LEFT_FRACTION * box.width;

      // The mask's left edge tracks the page gutter, so "WAHL." is cut as it
      // leaves the page rather than dissolving in place. It lands exactly on
      // the glyph once the C has arrived.
      const hiddenLeft =
        box.width === 0
          ? 0
          : clampProgress((PINNED_INSET - elementLeft) / box.width) * 100;
      const hiddenRight = lerp(
        0,
        (1 - GLYPH_RIGHT_FRACTION) * 100,
        retractRight,
      );
      const visibleRight = 100 - hiddenRight;

      // Each edge fades in from nothing as its cut starts to move and back to
      // nothing as the cut arrives at the glyph. So the mark at rest and the
      // pinned C are both exactly as crisp as an unmasked logo, and only the
      // part on its way out is ever soft — a fade across the C's own edge
      // would just make the pinned logo look out of focus.
      const leftFade = Math.max(
        0,
        Math.min(EDGE_FADE, hiddenLeft, GLYPH_LEFT_FRACTION * 100 - hiddenLeft),
      );
      const rightFade = Math.max(
        0,
        Math.min(
          EDGE_FADE,
          hiddenRight,
          visibleRight - GLYPH_RIGHT_FRACTION * 100,
        ),
      );

      left.set(elementLeft);
      width.set(box.width);
      height.set(box.height);
      maskImage.set(
        `linear-gradient(to right, transparent ${percent(hiddenLeft)}, #000 ${percent(hiddenLeft + leftFade)}, #000 ${percent(visibleRight - rightFade)}, transparent ${percent(visibleRight)})`,
      );
    },
  });

  const logo = <Logo variant="large" className="size-full" />;

  return (
    <>
      {/* Invisible, out of flow: only here so the morph can read width/left
          from CSS. Height is PINNED_HEIGHT so the C and the pinned pill stay
          the same size. left-5 matches the page gutter (px-5), which is also
          PINNED_INSET — absolute left-0 would sit on the padding edge and
          measure 20px too far left. */}
      <div
        ref={placeholderRef}
        className="pointer-events-none invisible absolute left-5 top-0 aspect-[880/114]"
        style={{ height: PINNED_HEIGHT }}
        aria-hidden="true"
      />
      {isReady ? (
        // pointer-events-none because a mask, unlike clip-path, leaves the
        // masked-away box still hit-testable.
        <m.div
          className="pointer-events-none fixed z-50 origin-top-left"
          style={{
            top: PINNED_TOP,
            left,
            width,
            height,
            maskImage,
            WebkitMaskImage: maskImage,
          }}
        >
          {logo}
        </m.div>
      ) : (
        <div
          className="pointer-events-none fixed z-50 aspect-[880/114] origin-top-left"
          style={{
            top: PINNED_TOP,
            left: PINNED_INSET,
            height: PINNED_HEIGHT,
          }}
        >
          {logo}
        </div>
      )}
    </>
  );
}

export default HeroLogo;

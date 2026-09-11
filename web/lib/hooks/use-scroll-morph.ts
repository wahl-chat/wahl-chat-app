'use client';

import { useMotionValueEvent, useScroll } from 'motion/react';
import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Tracks an element's position as it scrolls towards the top of the viewport,
 * so a caller can morph it into something pinned there.
 *
 * Progress is driven straight off the scroll position rather than a class that
 * flips at a threshold: that is what lets a morph run in both directions,
 * widening and returning as the visitor scrolls back up instead of snapping.
 * Nothing is spring-damped for the same reason — a spring would lag behind the
 * finger and overshoot on the way back.
 *
 * The caller writes its own motion values inside `onUpdate` rather than
 * deriving them with useTransform. That matters on resize: progress usually
 * does not change when the window does, so a derived transform would never
 * re-run and the element would keep a position computed for the old viewport.
 * Calling onUpdate from both the scroll handler and the measure pass means
 * every value is recomputed whenever either input moves.
 *
 * The caller keeps an empty placeholder in the document flow (attach `ref`) to
 * hold the space open, and renders the real element `fixed` once `isReady` is
 * true. Before that it should render in normal flow, which is what the server
 * sends and what a visitor without JavaScript keeps. That placeholder must be
 * sized in CSS, not from a measurement written back as an inline style — the
 * measurement would then only ever read back its own stale value and could not
 * follow a breakpoint.
 */

export type MorphBox = {
  /** Document coordinates, so it survives scrolling. */
  top: number;
  left: number;
  width: number;
  height: number;
};

export type MorphState = {
  progress: number;
  /** Where the element would sit had it stayed in the document flow. */
  restTop: number;
  box: MorphBox;
};

type Options = {
  /** Where the element comes to rest. */
  pinnedTop: number;
  /**
   * Distance from the viewport top at which the morph begins. Suits elements
   * that start well down the page and scroll up into the corner.
   */
  startTop?: number;
  /**
   * Scroll distance the morph runs over, used instead of startTop for an
   * element that already sits near the top — there the gap to the viewport
   * edge is only a few dozen pixels, so a viewport-based range would be
   * complete before the visitor has scrolled at all.
   */
  morphDistance?: number;
  onUpdate: (state: MorphState) => void;
};

export const clampProgress = (value: number) => Math.min(1, Math.max(0, value));
export const lerp = (from: number, to: number, t: number) =>
  from + (to - from) * t;

export function useScrollMorph({
  pinnedTop,
  startTop,
  morphDistance,
  onUpdate,
}: Options) {
  const placeholderRef = useRef<HTMLDivElement>(null);
  const boxRef = useRef<MorphBox | null>(null);
  const [isReady, setIsReady] = useState(false);

  const { scrollY } = useScroll();

  // Held in a ref so a caller can pass an inline callback without the effect
  // below tearing down and re-attaching its listeners on every render.
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;

  const apply = useCallback(
    (scrolled: number) => {
      const box = boxRef.current;
      if (!box) return;

      const restTop = box.top - scrolled;
      const progress = morphDistance
        ? clampProgress(scrolled / morphDistance)
        : clampProgress(
            ((startTop ?? 0) - restTop) / ((startTop ?? 0) - pinnedTop),
          );

      onUpdateRef.current({ progress, restTop, box });
    },
    [pinnedTop, startTop, morphDistance],
  );

  const measure = useCallback(() => {
    const element = placeholderRef.current;
    if (!element) return;

    const rect = element.getBoundingClientRect();
    boxRef.current = {
      top: rect.top + window.scrollY,
      left: rect.left,
      width: rect.width,
      height: rect.height,
    };

    apply(window.scrollY);
    setIsReady(true);
  }, [apply]);

  useEffect(() => {
    measure();

    // The ResizeObserver catches reflow; the window listeners catch the cases
    // it does not, above all a viewport change that leaves the body's own box
    // untouched — dragging the window to a second screen being the one that
    // started this.
    const observer = new ResizeObserver(measure);
    observer.observe(document.body);
    window.addEventListener('resize', measure);
    window.addEventListener('orientationchange', measure);

    return () => {
      observer.disconnect();
      window.removeEventListener('resize', measure);
      window.removeEventListener('orientationchange', measure);
    };
  }, [measure]);

  useMotionValueEvent(scrollY, 'change', apply);

  return { placeholderRef, isReady };
}

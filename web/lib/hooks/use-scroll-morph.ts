'use client';

import { useMotionValue, useMotionValueEvent, useScroll } from 'motion/react';
import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Tracks an element's position as it scrolls towards the top of the viewport,
 * so a caller can morph it into something pinned there.
 *
 * The output is a progress value driven straight off the scroll position
 * rather than a class that flips at a threshold: that is what lets a morph run
 * in both directions, widening and returning as the visitor scrolls back up
 * instead of snapping. Nothing is spring-damped for the same reason — a spring
 * would lag behind the finger and overshoot on the way back.
 *
 * The caller keeps an empty placeholder in the document flow (attach `ref` to
 * it) to hold the space open, and renders the real element `fixed` once
 * `isReady` is true. Before that it should render in normal flow, which is
 * what the server sends and what a visitor without JavaScript keeps.
 */

export type MorphBox = {
  /** Document coordinates, so it survives scrolling. */
  top: number;
  left: number;
  width: number;
  height: number;
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
};

export const clampProgress = (value: number) => Math.min(1, Math.max(0, value));
export const lerp = (from: number, to: number, t: number) =>
  from + (to - from) * t;

export function useScrollMorph({
  pinnedTop,
  startTop,
  morphDistance,
}: Options) {
  const placeholderRef = useRef<HTMLDivElement>(null);
  const boxRef = useRef<MorphBox | null>(null);
  const [isReady, setIsReady] = useState(false);

  const { scrollY } = useScroll();
  const progress = useMotionValue(0);
  /** Where the element would sit had it stayed in the document flow. */
  const restTop = useMotionValue(0);

  const apply = useCallback(
    (scrolled: number) => {
      const box = boxRef.current;
      if (!box) return;

      const currentTop = box.top - scrolled;
      restTop.set(currentTop);
      progress.set(
        morphDistance
          ? clampProgress(scrolled / morphDistance)
          : clampProgress(
              ((startTop ?? 0) - currentTop) / ((startTop ?? 0) - pinnedTop),
            ),
      );
    },
    [progress, restTop, startTop, pinnedTop, morphDistance],
  );

  const measure = useCallback(() => {
    const element = placeholderRef.current;
    if (!element) return;

    const rect = element.getBoundingClientRect();
    boxRef.current = {
      top: rect.top + window.scrollY,
      left: rect.left,
      width: rect.width,
      // Kept from the first measurement: once the element is pinned the
      // placeholder is empty, so its own height reserves nothing.
      height: boxRef.current?.height ?? rect.height,
    };

    apply(window.scrollY);
    setIsReady(true);
  }, [apply]);

  useEffect(() => {
    measure();

    const observer = new ResizeObserver(measure);
    observer.observe(document.body);
    return () => observer.disconnect();
  }, [measure]);

  useMotionValueEvent(scrollY, 'change', apply);

  return { placeholderRef, boxRef, isReady, progress, restTop };
}

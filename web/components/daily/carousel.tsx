'use client';

import { useRef, useState } from 'react';

/**
 * Which slide of a horizontal scroll-snap strip is in view. The index is
 * derived from the scroll position, so swiping and trackpads stay in sync.
 */
export function useSnapCarousel(gap: number) {
  const ref = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(0);

  const onScroll = () => {
    const el = ref.current;
    const first = el?.firstElementChild as HTMLElement | null;
    if (!el || !first) {
      return;
    }
    setActive(Math.round(el.scrollLeft / (first.offsetWidth + gap)));
  };

  return { ref, active, onScroll };
}

'use client';

import {
  type ScrollEdges,
  edgeFadeMask,
  scrollEdges,
} from '@/lib/daily/scroll-edges';
import { cn } from '@/lib/utils';
import { ChevronLeftIcon, ChevronRightIcon } from 'lucide-react';
import {
  type ReactNode,
  type RefObject,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import { FOCUS_RING } from './card-styles';

const CHEVRON =
  'absolute top-1/2 z-10 flex size-8 -translate-y-1/2 items-center justify-center rounded-full border border-[var(--daily-border)] bg-[var(--daily-canvas)] text-[var(--daily-ink)] shadow-sm transition-colors hover:bg-[var(--daily-surface)]';

/**
 * A sideways-scrolling row that shows there is more: the cut-off side fades
 * out and gets a chevron that scrolls one `step`. It bleeds to the screen
 * edge like the rest of the feed's rows (``-mx-4``), so content still starts
 * on the column's left edge; inside a container that already bleeds, pass
 * `bleed={false}`.
 */
export function ScrollRow({
  children,
  className,
  step,
  label,
  scrollerRef,
  onScroll,
  bleed = true,
}: {
  children: ReactNode;
  /** Extra classes for the scrolling element (gap, snapping). */
  className?: string;
  /** How far one chevron press scrolls, from the scroller. */
  step: (scroller: HTMLDivElement) => number;
  /** What the row holds, for the chevrons' labels: "Themen", "Debatten". */
  label: string;
  scrollerRef?: RefObject<HTMLDivElement | null>;
  onScroll?: () => void;
  bleed?: boolean;
}) {
  const ownRef = useRef<HTMLDivElement>(null);
  const ref = scrollerRef ?? ownRef;
  const [edges, setEdges] = useState<ScrollEdges>({ start: false, end: false });

  const measure = useCallback(() => {
    const el = ref.current;
    if (el) {
      setEdges(scrollEdges(el.scrollLeft, el.clientWidth, el.scrollWidth));
    }
  }, [ref]);

  useEffect(() => {
    const el = ref.current;
    if (!el) {
      return;
    }
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    for (const child of Array.from(el.children)) {
      observer.observe(child);
    }
    return () => observer.disconnect();
  }, [ref, measure]);

  const scroll = (direction: 1 | -1) => {
    const el = ref.current;
    if (!el) {
      return;
    }
    const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    el.scrollBy({
      left: direction * step(el),
      behavior: still ? 'auto' : 'smooth',
    });
  };

  const mask = edgeFadeMask(edges);
  return (
    <div className={cn('relative', bleed && '-mx-4')}>
      <div
        ref={ref}
        onScroll={() => {
          measure();
          onScroll?.();
        }}
        style={mask ? { maskImage: mask, WebkitMaskImage: mask } : undefined}
        className={cn(
          'flex overflow-x-auto px-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden',
          className,
        )}
      >
        {children}
      </div>
      {edges.start && (
        <button
          type="button"
          aria-label={`${label}: zurück`}
          onClick={() => scroll(-1)}
          className={cn(CHEVRON, FOCUS_RING, 'left-1')}
        >
          <ChevronLeftIcon aria-hidden className="size-4" />
        </button>
      )}
      {edges.end && (
        <button
          type="button"
          aria-label={`${label}: weiter`}
          onClick={() => scroll(1)}
          className={cn(CHEVRON, FOCUS_RING, 'right-1')}
        >
          <ChevronRightIcon aria-hidden className="size-4" />
        </button>
      )}
    </div>
  );
}

/** One page of a row: most of its visible width, so a sliver of what came
 * before stays in view. */
export function pageStep(scroller: HTMLDivElement): number {
  return scroller.clientWidth * 0.8;
}

/** One slide of a carousel, gap included. */
export function slideStep(gap: number) {
  return (scroller: HTMLDivElement): number => {
    const first = scroller.firstElementChild as HTMLElement | null;
    return (first?.offsetWidth ?? scroller.clientWidth) + gap;
  };
}

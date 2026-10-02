'use client';

import { cn } from '@/lib/utils';
import { useRef, useState } from 'react';

/**
 * State for a horizontal scroll-snap strip: which slide is in view, and a way
 * to jump to one. The index is derived from the scroll position, so swiping,
 * trackpads and the dots all stay in sync.
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

  const goTo = (index: number) => {
    const slide = ref.current?.children[index] as HTMLElement | undefined;
    slide?.scrollIntoView({
      behavior: 'smooth',
      block: 'nearest',
      inline: 'start',
    });
  };

  return { ref, active, onScroll, goTo };
}

export function CarouselDots({
  labels,
  active,
  onSelect,
  className,
}: {
  /** One accessible name per slide. */
  labels: string[];
  active: number;
  onSelect: (index: number) => void;
  className?: string;
}) {
  return (
    <div className={cn('flex items-center justify-center gap-2', className)}>
      {labels.map((label, i) => (
        <button
          // Labels can repeat (two speeches by one person); the index is the
          // slide's identity.
          // biome-ignore lint/suspicious/noArrayIndexKey: slides are positional
          key={i}
          type="button"
          aria-label={`${label} anzeigen`}
          aria-current={active === i}
          onClick={() => onSelect(i)}
          className={cn(
            'h-2.5 rounded-full border-2 border-[var(--daily-ink)] transition-[width] motion-reduce:transition-none',
            active === i ? 'w-6 bg-[var(--daily-ink)]' : 'w-2.5',
          )}
        />
      ))}
    </div>
  );
}

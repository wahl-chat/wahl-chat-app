'use client';

import { ContextIcon } from '@/components/context-icon';
import { Button } from '@/components/ui/button';
import type { Context } from '@/lib/firebase/firebase.types';
import { lerp, useScrollMorph } from '@/lib/hooks/use-scroll-morph';
import { cn } from '@/lib/utils';
import { ArrowRightIcon } from 'lucide-react';
import { m, useTransform } from 'motion/react';
import Link from 'next/link';

/**
 * The hero call to action, which shrinks and pins itself to the top right as
 * it scrolls out of the hero. See useScrollMorph for why this tracks the
 * scroll position rather than flipping at a threshold.
 */

import {
  PINNED_HEIGHT,
  PINNED_INSET,
  PINNED_TOP,
} from '@/components/landing/pinned-layout';

/** Wide enough for the label at its natural size; verified against wrapping. */
const PINNED_WIDTH = 250;
/** The morph runs over the last stretch before the button reaches the top. */
const MORPH_START_TOP = 140;

function HeroCta({ context }: { context: Context }) {
  const { placeholderRef, boxRef, isReady, progress, restTop } = useScrollMorph(
    { startTop: MORPH_START_TOP, pinnedTop: PINNED_TOP },
  );

  const top = useTransform(restTop, (value) => Math.max(value, PINNED_TOP));
  // useTransform evaluates during render, including on the server, so the
  // viewport width has to be guarded — there is no window there.
  const left = useTransform(progress, (p) =>
    typeof window === 'undefined'
      ? 0
      : lerp(
          boxRef.current?.left ?? 0,
          window.innerWidth - PINNED_WIDTH - PINNED_INSET,
          p,
        ),
  );
  const width = useTransform(progress, (p) =>
    lerp(boxRef.current?.width ?? 0, PINNED_WIDTH, p),
  );
  // Comes down from its natural 56px to meet the mark's pinned height.
  const height = useTransform(progress, (p) =>
    lerp(boxRef.current?.height ?? 0, PINNED_HEIGHT, p),
  );

  // Two variants rather than one: in flow the button sizes itself from its
  // padding, while pinned it fills the wrapper whose height is being animated.
  // At progress 0 the wrapper is exactly the natural height, so they coincide.
  const button = (fillsWrapper: boolean) => (
    <Button
      asChild
      size="lg"
      className={cn(
        'w-full whitespace-nowrap rounded-full px-6 text-base shadow-lg',
        fillsWrapper ? 'h-full py-0' : 'h-auto py-4',
      )}
    >
      {/* The visible label is deliberately short, so the link carries the
          election in its accessible name — "Jetzt informieren" on its own
          tells a screen-reader user navigating by links nothing about where
          it goes. */}
      <Link
        href={`/${context.context_id}`}
        aria-label={`Jetzt zur ${context.name} informieren`}
      >
        <ContextIcon context={context} className="size-6 shrink-0" />
        <span>Jetzt informieren</span>
        <ArrowRightIcon aria-hidden="true" />
      </Link>
    </Button>
  );

  return (
    <div
      ref={placeholderRef}
      className="w-full max-w-md"
      style={isReady ? { height: boxRef.current?.height } : undefined}
    >
      {isReady ? (
        <m.div className="fixed z-50" style={{ top, left, width, height }}>
          {button(true)}
        </m.div>
      ) : (
        button(false)
      )}
    </div>
  );
}

export default HeroCta;

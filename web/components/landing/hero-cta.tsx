'use client';

import { ContextIcon } from '@/components/context-icon';
import {
  HERO_CTA_HEIGHT,
  PINNED_HEIGHT,
  PINNED_INSET,
  PINNED_TOP,
} from '@/components/landing/pinned-layout';
import { Button } from '@/components/ui/button';
import type { Context } from '@/lib/firebase/firebase.types';
import { lerp, useScrollMorph } from '@/lib/hooks/use-scroll-morph';
import { ArrowRightIcon } from 'lucide-react';
import { m, useMotionValue } from 'motion/react';
import Link from 'next/link';

/**
 * The hero call to action, which shrinks and pins itself to the top right as
 * it scrolls out of the hero. See useScrollMorph for why this tracks the
 * scroll position rather than flipping at a threshold, and why the values are
 * written in onUpdate rather than derived.
 */

/** Wide enough for the label at its natural size; verified against wrapping. */
const PINNED_WIDTH = 250;
/** The morph runs over the last stretch before the button reaches the top. */
const MORPH_START_TOP = 140;

function HeroCta({ context }: { context: Context }) {
  const top = useMotionValue(0);
  const left = useMotionValue(0);
  const width = useMotionValue(0);
  const height = useMotionValue(0);

  const { placeholderRef, isReady } = useScrollMorph({
    pinnedTop: PINNED_TOP,
    startTop: MORPH_START_TOP,
    onUpdate: ({ progress, restTop, box }) => {
      top.set(Math.max(restTop, PINNED_TOP));
      // Read at update time, not render time: on a resize this is the only
      // thing that has changed, and it has to reach the pinned position.
      left.set(
        lerp(
          box.left,
          window.innerWidth - PINNED_WIDTH - PINNED_INSET,
          progress,
        ),
      );
      width.set(lerp(box.width, PINNED_WIDTH, progress));
      // Comes down from its hero height to meet the mark's pinned height.
      height.set(lerp(box.height, PINNED_HEIGHT, progress));
    },
  });

  const button = (
    <Button
      asChild
      size="lg"
      className="size-full whitespace-nowrap rounded-full px-6 py-0 text-base shadow-lg"
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
    // Sized in CSS so it keeps reserving the right space and keeps measuring
    // honestly, whatever the viewport does.
    <div
      ref={placeholderRef}
      className="w-full max-w-md"
      style={{ height: HERO_CTA_HEIGHT }}
    >
      {isReady ? (
        <m.div className="fixed z-50" style={{ top, left, width, height }}>
          {button}
        </m.div>
      ) : (
        button
      )}
    </div>
  );
}

export default HeroCta;

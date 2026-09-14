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
import { cn } from '@/lib/utils';
import { ArrowRightIcon } from 'lucide-react';
import { m, useMotionValue } from 'motion/react';
import Link from 'next/link';

/**
 * The hero call to action, which shrinks and pins itself to the top right as
 * it scrolls out of the hero.
 *
 * Nothing here positions the button vertically while it is on its way up: it
 * rides inside its placeholder, in the document flow, and the browser moves it.
 * Only the horizontal travel and the size are driven from the scroll, and only
 * once it has arrived does it go `fixed` at a constant top. See useScrollMorph
 * for why — in short, a `fixed` element positioned from `scrollY` is always a
 * frame behind the page, and that shows up as a wobble under a flick.
 */

/** Wide enough for the label at its natural size; verified against wrapping. */
const PINNED_WIDTH = 250;
/** The morph runs over the last stretch before the button reaches the top. */
const MORPH_START_TOP = 140;

function HeroCta({ context }: { context: Context }) {
  // Horizontal offset from the placeholder, not an absolute left: in flow the
  // button is placed by its parent, and a transform moves it from there
  // without disturbing anything around it.
  const x = useMotionValue(0);
  const width = useMotionValue<number | string>('100%');
  const height = useMotionValue<number | string>('100%');

  const { placeholderRef, isReady, isPinned } = useScrollMorph({
    pinnedTop: PINNED_TOP,
    startTop: MORPH_START_TOP,
    onUpdate: ({ progress, box }) => {
      // Read at update time, not render time: on a resize this is the only
      // thing that has changed, and it has to reach the pinned position.
      const pinnedLeft = window.innerWidth - PINNED_WIDTH - PINNED_INSET;

      x.set(lerp(0, pinnedLeft - box.left, progress));
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
      className="relative w-full max-w-md"
      style={{ height: HERO_CTA_HEIGHT }}
    >
      {isReady ? (
        // One element across both phases, never two branches: swapping the
        // tree here would unmount and remount the link, dropping its DOM node
        // (and any focus on it) mid-scroll.
        <m.div
          className={cn('z-50', isPinned ? 'fixed' : 'absolute left-0 top-0')}
          style={
            isPinned
              ? { top: PINNED_TOP, right: PINNED_INSET, width, height }
              : { x, width, height }
          }
        >
          {button}
        </m.div>
      ) : (
        button
      )}
    </div>
  );
}

export default HeroCta;

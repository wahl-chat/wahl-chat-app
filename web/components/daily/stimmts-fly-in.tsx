'use client';

import { flipTransform } from '@/lib/stimmts/flip';
import { browserSession, clearJustPlayed } from '@/lib/stimmts/presence';
import { useReducedMotion } from 'motion/react';
import { type ReactNode, useEffect, useRef } from 'react';

/** Marks the header icon, the flight's target. */
export const ICON_TARGET_ATTRIBUTE = 'data-stimmts-icon';

/** Fired on window when the card has reached the icon (or faded out). */
export const ICON_LANDED_EVENT = 'stimmts:icon-landed';

/** How long the card shows the result before it leaves. */
const HOLD_MS = 600;
const FLIGHT_MS = 600;
const FADE_MS = 200;
const EASE_OUT = 'cubic-bezier(0.22, 1, 0.36, 1)';

function visibleIcon(): HTMLElement | null {
  const icon = document.querySelector<HTMLElement>(
    `[${ICON_TARGET_ATTRIBUTE}]`,
  );
  return icon && icon.getClientRects().length > 0 ? icon : null;
}

/**
 * Collapses the slot together with the card, gap included, so the feed
 * closes up smoothly instead of jumping by the gap when the slot unmounts.
 */
function collapse(slot: HTMLElement, duration: number): Animation {
  const gap = Number.parseFloat(
    getComputedStyle(slot.parentElement ?? slot).rowGap,
  );
  const height = slot.offsetHeight;
  return slot.animate(
    [
      { height: `${height}px`, marginBottom: '0px' },
      { height: '0px', marginBottom: `${-(Number.isNaN(gap) ? 0 : gap)}px` },
    ],
    { duration, easing: EASE_OUT, fill: 'forwards' },
  );
}

async function fly(card: HTMLElement, slot: HTMLElement, icon: HTMLElement) {
  const { x, y, scale } = flipTransform(
    card.getBoundingClientRect(),
    icon.getBoundingClientRect(),
  );
  // Above the sticky header, which the card passes on its way up.
  card.style.position = 'relative';
  card.style.zIndex = '40';
  const options: KeyframeAnimationOptions = {
    duration: FLIGHT_MS,
    easing: EASE_OUT,
    fill: 'forwards',
  };
  const flight = card.animate(
    [
      { transform: 'none', opacity: 1 },
      { transform: `translate(${x}px, ${y}px) scale(${scale})`, opacity: 0 },
    ],
    options,
  );
  collapse(slot, FLIGHT_MS);
  const appear = icon.animate([{ opacity: 0 }, { opacity: 1 }], options);
  await flight.finished;
  return appear;
}

/**
 * The reduced-motion exit: the card only fades, and the slot closes with it,
 * so the feed below does not snap up when the slot unmounts. The slot clips
 * the card while it closes, so the card itself never moves.
 */
export async function fade(
  card: HTMLElement,
  slot: HTMLElement,
  icon: HTMLElement | null,
) {
  const options: KeyframeAnimationOptions = {
    duration: FADE_MS,
    fill: 'forwards',
  };
  slot.style.overflow = 'hidden';
  const out = card.animate([{ opacity: 1 }, { opacity: 0 }], options);
  collapse(slot, FADE_MS);
  const appear = icon?.animate([{ opacity: 0 }, { opacity: 1 }], options);
  await out.finished;
  return appear;
}

/**
 * Right after a game, the feed card shows the result for a moment and then
 * shrinks into the header icon, so the player learns where the result lives
 * from now on. Readers who asked for less motion see it fade instead. Either
 * way it plays once: the flag is cleared when it ends.
 */
function StimmtsFlyIn({
  children,
  onDone,
}: {
  children: ReactNode;
  onDone: () => void;
}) {
  const slot = useRef<HTMLDivElement>(null);
  const reduceMotion = useReducedMotion() ?? false;
  // The sequence starts once; a later change of the motion setting or a new
  // callback must not restart it halfway.
  const settings = useRef({ reduceMotion, onDone });
  settings.current = { reduceMotion, onDone };

  useEffect(() => {
    let cancelled = false;
    const box = slot.current;
    const timer = setTimeout(async () => {
      const box = slot.current;
      const card = box?.firstElementChild;
      if (!box || !(card instanceof HTMLElement)) {
        return;
      }
      const icon = visibleIcon();
      let appear: Animation | undefined;
      try {
        appear =
          settings.current.reduceMotion || !icon
            ? await fade(card, box, icon)
            : await fly(card, box, icon);
      } catch {
        // An animation cancelled by leaving the page: nothing left to show.
      }
      if (cancelled) {
        return;
      }
      clearJustPlayed(browserSession(), document.documentElement);
      // The icon's own style takes over now that the flag is gone.
      appear?.cancel();
      window.dispatchEvent(new Event(ICON_LANDED_EVENT));
      settings.current.onDone();
    }, HOLD_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
      // Left mid-flight: the mark would keep hiding the icon's check on the
      // next page. The session flag stays, so a reload still shows the
      // flight the player missed. The check runs once React has detached
      // the slot, so a development remount (the slot still in place) keeps
      // the mark.
      setTimeout(() => {
        if (!box?.isConnected) {
          delete document.documentElement.dataset.stimmtsFly;
        }
      }, 0);
    };
  }, []);

  return <div ref={slot}>{children}</div>;
}

export default StimmtsFlyIn;
